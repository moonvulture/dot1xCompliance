#!/usr/bin/env python3

from ttp import ttp
import json
import logging
from pathlib import Path
from datetime import datetime
from elasticsearch import Elasticsearch, helpers
import os

def load_env_vars(env_file):
    env = {}
    with open(env_file) as f:
        for line in f:
            if "=" in line:
                key, val = line.strip().split("=", 1)
                env[key.strip()] = val.strip()
    return env

def get_es_client():
    env = load_env_vars("secrets.env")
    es_host = env.get("ES_HOST")
    es_user = env.get("ES_USER")
    es_pass = env.get("ES_PASS")
    # For SSL self-signed, set verify_certs=False (not recommended for prod)
    es = Elasticsearch(
        es_host,
        basic_auth=(es_user, es_pass),
        verify_certs=True,
        timeout=30,
    )
    return es

def to_ecs(issue):
    return {
        "@timestamp": issue["@timestamp"],
        "host": {"name": issue["hostname"]},
        "network": {"interface": issue["interface"]},
        "event": {
            "kind": "alert" if not issue["is_compliant"] else "event",
            "category": ["configuration"],
            "type": ["compliance"]
        },
        "rule": {
            "id": "dot1x_compliance",
            "name": "802.1X Access Port Compliance"
        },
        "message": issue["issue"],
        "dot1x": {
            "enabled": issue.get("dot1x_enabled"),
            "exempt": issue.get("is_exempt"),
            "description": issue.get("description", "")
        },
        "compliance": {
            "status": "passed" if issue["is_compliant"] else "failed"
        },
        "tags": ["dot1x", "network", "compliance"]
    }

def elasticsearch_ingest(ndjson_dir="ndjson", index="dot1x-compliance"):
    es = get_es_client()
    ndjson_path = Path(ndjson_dir)
    all_issues = []
    for file in ndjson_path.glob("*.json"):
        with file.open() as f:
            for line in f:
                issue = json.loads(line)
                ecs_doc = to_ecs(issue)
                all_issues.append({"_index": index, "_source": ecs_doc})

    # Bulk ingest
    if all_issues:
        helpers.bulk(es, all_issues)
        logger.info(f"Pushed {len(all_issues)} docs to {index} index")
    else:
        logger.info("No compliance issues to ingest.")


def setup_logger():
    logger = logging.getLogger("dot1xCompliance")
    logger.setLevel(logging.INFO)
    handler = logging.StreamHandler()
    formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(message)s", "%Y-%m-%d %H:%M:%S"
    )
    handler.setFormatter(formatter)
    logger.handlers.clear()
    logger.addHandler(handler)
    return logger

logger = setup_logger()

def parse_switch_config(config_text):
    """Parse switch configuration and check 802.1X compliance"""

    # TTP template to extract interface configurations
    template = """
<group name="metadata">
hostname {{ hostname }}
</group>
<group name="interfaces">
interface {{ interface_name }}
 description {{ description | re(".*") }}
 switchport mode access {{ is_access_port | set(True) }}
 dot1x pae authenticator {{ dot1x_enabled | set(True) }}
 dot1x port-control auto {{ dot1x_control | set(True) }}
</group>
    """

    # Parse the configuration
    parser = ttp(data=config_text, template=template)
    parser.parse()
    results = parser.result()
    logger.info(f"TTP raw results: {results}")
    if not results or not results[0]:
        return []

    # Extract hostname
    metadata = results[0][0].get('metadata', [])
    hostname = "UNKNOWN"
    if metadata:
        # metadata might be a list of dicts
        md = metadata[0] if isinstance(metadata, list) else metadata
        hostname = md.get("hostname", "UNKNOWN")

    interfaces = results[0][0].get('interfaces', [])
    if not isinstance(interfaces, list):
        interfaces = [interfaces] if interfaces else []

    # Step 1: Get list of access ports
    access_ports = [intf for intf in interfaces if intf.get('is_access_port')]

    logger.info(f"Found {len(access_ports)} access ports on {hostname}")

    # Step 2-4: Check compliance for each access port
    non_compliant_interfaces = []
    compliant_interfaces = []


    for intf in access_ports:
        interface_name = intf.get('interface_name', 'Unknown')
        dot1x_enabled = intf.get('dot1x_enabled', False) or intf.get('dot1x_control', False)
        description = intf.get('description', '').strip().lower()
        is_exempt = '802.1x exempt' in description or '802.1x exemption' in description

        # Step 2: Check if dot1x is enabled
        if dot1x_enabled or is_exempt:
            compliant_issue = {
                'hostname': hostname,
                'interface': interface_name,
                'issue': '802.1X Compliant',
                'description': intf.get('description', ''),
                'dot1x_enabled': bool(dot1x_enabled),
                'is_exempt': bool(is_exempt),
                'is_compliant': True
            }
            compliant_interfaces.append(compliant_issue)
            logger.info(f"Compliant: {interface_name} - 802.1X enabled or exempt")
        else:
            compliance_issue = {
                'hostname': hostname,
                'interface': interface_name,
                'issue': '802.1X NonCompliant',
                'description': intf.get('description', ''),
                'dot1x_enabled': False,
                'is_exempt': False,
                'is_compliant': False
            }
            non_compliant_interfaces.append(compliance_issue)
            logger.warning(f"Non-compliant: {interface_name} - No 802.1X, no exemption")
        
    return compliant_interfaces, non_compliant_interfaces, hostname

def process_config_files(config_dir='configs', output_dir='ndjson'):
    """Process all configuration files in the directory"""

    config_path = Path(config_dir)
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    config_files = list(config_path.glob('*.cfg'))

    if not config_files:
        logger.error(f"No .cfg files found in {config_path.resolve()}/")
        return

    all_non_compliant = []

    for config_file in config_files:
        logger.info(f"\nProcessing {config_file.name}")
        try:
            config_text = config_file.read_text()
            compliant, non_compliant, hostname = parse_switch_config(config_text)

            # Save compliant ports
            ndjson_file_compliant = output_path / f"{hostname}_compliant.json"
            now = datetime.utcnow().isoformat() + "Z"
            with ndjson_file_compliant.open('w') as f:
                for issue in compliant:
                    issue['@timestamp'] = now
                    issue['report_date'] = now[:10]
                    f.write(json.dumps(issue) + '\n')

            # Save non-compliant ports
            ndjson_file_noncompliant = output_path / f"{hostname}_noncompliant.json"
            with ndjson_file_noncompliant.open('w') as f:
                for issue in non_compliant:
                    issue['@timestamp'] = now
                    issue['report_date'] = now[:10]
                    f.write(json.dumps(issue) + '\n')

            logger.info(f"Created {ndjson_file_compliant} ({len(compliant)} compliant), {ndjson_file_noncompliant} ({len(non_compliant)} non-compliant)")

            all_non_compliant.extend(non_compliant)

        except Exception as e:
            logger.error(f"Error processing {config_file}: {e}")

    # Summary report (unchanged)
    logger.info("\nCOMPLIANCE SUMMARY")
    logger.info(f"Total non-compliant interfaces: {len(all_non_compliant)}")

    if all_non_compliant:
        logger.info("\nNon-compliant interfaces:")
        for issue in all_non_compliant:
            logger.warning(f"  • {issue['hostname']} - {issue['interface']}: {issue['issue']}")
    else:
        logger.info("All access ports are compliant!")

    return all_non_compliant
def main():
    logger.info("Starting 802.1X Compliance Check")
    logger.info("=" * 50)
    non_compliant_interfaces = process_config_files()
    logger.info("\nCompliance check complete!")
    logger.info(f"Check the ndjson/ directory for Elasticsearch-ready output files.")

if __name__ == "__main__":
    main()
    elasticsearch_ingest()