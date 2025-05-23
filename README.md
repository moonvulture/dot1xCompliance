# Writing README.md to a downloadable file
# STIG 802.1X Compliance Parser

A simple toolchain to parse daily Cisco switch configuration backups using **pyATS & Genie**, evaluate 802.1X compliance per interface, and output NDJSON for ingestion into Elasticsearch via Filebeat.

---

## 🛠️ Prerequisites

- Python 3.8+ and virtualenv
- pyATS & Genie
- Elasticsearch (7.x or newer) & Kibana
- Filebeat 7.x or newer

---

## ⚙️ Installation

1. **Clone the repository**

   ```bash
   git clone https://your-repo-url/stig-dot1x-parser.git
   cd stig-dot1x-parser
   ```

2. **Create & activate a virtual environment**

   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```

3. **Install dependencies**

   ```bash
   pip install pyats genie
   ```

---

## 📂 Project Structure

```text
stig-dot1x-parser/
├── configs/          # Raw daily config backups (.txt)
├── ndjson/           # Generated NDJSON files for Filebeat
├── parse.py          # Parser script using pyATS & Genie
├── filebeat.yml      # Filebeat input & Elasticsearch output config
└── elastic-template.json  # Elasticsearch index template & mapping
```

---

## 🚀 Usage

1. **Place your Cisco IOS config files** in the `configs/` directory. Filenames should follow:
   `hostname_config.txt` (e.g. `sw1_config.txt`).

2. **Run the parser** to generate NDJSON:

   ```bash
   python parse.py
   ```

   - Reads each `*.txt` in `configs/`
   - Uses **pyATS & Genie** to parse interface blocks
   - Evaluates STIG 802.1X rules (access port + dot1x or exempt)
   - Outputs one NDJSON file per host in `ndjson/`

3. **Configure Filebeat** (`filebeat.yml`):

   ```yaml
   filebeat.inputs:
     - type: filestream
       paths:
         - ./ndjson/*.json
       parsers:
         - ndjson:
             expand_keys: true

   output.elasticsearch:
     hosts: ["http://localhost:9200"]
     index: "stig-dot1x-%{+yyyy.MM.dd}"
   ```

4. **Load Elasticsearch template**:

   ```bash
   curl -X PUT "localhost:9200/_index_template/stig-dot1x-template" \
     -H 'Content-Type: application/json' \
     -d @elastic-template.json
   ```

5. **Start Filebeat**:

   ```bash
   filebeat -e -c filebeat.yml
   ```

6. **Visualize in Kibana**:
   - Build dashboards with Lens: pie charts, line trends, data tables.

---

## 🔍 Elasticsearch Mapping

See `elastic-template.json` for the full mapping. Key fields:

- `@timestamp` (date)
- `switch.hostname` (keyword)
- `interface.name` (keyword)
- `interface.is_access_port` (boolean)
- `interface.dot1x_enabled` (boolean)
- `compliance.status` (keyword)
- `compliance.reason` (text)
- `report_date` (date)

---

## 🤝 Contributing

Feel free to submit issues or pull requests for enhancements:
- Add location enrichment
- Support other OS/platforms with Genie
- Extend compliance rules

---

## 📄 License

This project is released under the MIT License. See `LICENSE` for details.
"""
file_path = "/mnt/data/README.md"
with open(file_path, "w") as f:
    f.write(content)

file_path
