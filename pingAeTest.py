# enhanced_ping_test.py

from pyats import aetest
import re
import logging
from unicon.core.errors import SubCommandFailure, ConnectionError
from pyats.log.utils import banner

# Configure logging
logger = logging.getLogger(__name__)

class CommonSetup(aetest.CommonSetup):
    @aetest.subsection
    def connect_device(self, testbed):
        """Connect to the device and store it in parameters"""
        try:
            # Adjust device name as needed
            device = testbed.devices['Cat8K']
            logger.info(f"Connecting to device: {device.name}")
            device.connect(log_stdout=False)
            self.parent.parameters['device'] = device
            logger.info(f"Successfully connected to {device.name}")
        except ConnectionError as e:
            self.failed(f"Failed to connect to device: {e}")
        except Exception as e:
            self.failed(f"Unexpected error during connection: {e}")

class PingTestcase(aetest.Testcase):
    """Test various ping scenarios to validate network connectivity"""
    
    @aetest.test
    def ping_google_dns(self):
        """Test ping to Google's primary DNS server"""
        self._perform_ping_test('8.8.8.8', 'Google Primary DNS')
    
    @aetest.test
    def ping_google_secondary_dns(self):
        """Test ping to Google's secondary DNS server"""
        self._perform_ping_test('8.8.4.4', 'Google Secondary DNS')
    
    @aetest.test
    def ping_cloudflare_dns(self):
        """Test ping to Cloudflare DNS for redundancy"""
        self._perform_ping_test('1.1.1.1', 'Cloudflare DNS')
    
    @aetest.test
    def ping_with_extended_options(self):
        """Test ping with extended options (size, count, timeout)"""
        device = self.parameters['device']
        destination = '8.8.8.8'
        
        try:
            # Ping with specific parameters: 5 packets, 1500 byte size, 2 second timeout
            result = device.execute('ping 8.8.8.8 repeat 5 size 1500 timeout 2')
            logger.info(f"Extended ping result: {result}")
            
            # Parse success rate
            success_match = re.search(r'Success rate is (\d+) percent', result)
            # Parse round-trip times
            rtt_match = re.search(r'round-trip min/avg/max = (\d+)/(\d+)/(\d+) ms', result)
            
            if success_match:
                success_rate = int(success_match.group(1))
                logger.info(f"Success rate: {success_rate}%")
                
                if rtt_match:
                    min_rtt, avg_rtt, max_rtt = map(int, rtt_match.groups())
                    logger.info(f"RTT - Min: {min_rtt}ms, Avg: {avg_rtt}ms, Max: {max_rtt}ms")
                    
                    # Check for reasonable response times (less than 500ms average)
                    if avg_rtt > 500:
                        logger.warning(f"High average RTT detected: {avg_rtt}ms")
                
                if success_rate >= 80:  # Allow for some packet loss
                    self.passed(f'Extended ping to {destination} succeeded with {success_rate}% success rate')
                else:
                    self.failed(f'Extended ping to {destination} had low success rate: {success_rate}%')
            else:
                self.failed(f'Could not parse success rate from ping output: {result}')
                
        except SubCommandFailure as e:
            logger.error(f"Extended ping command failed: {e}")
            self.failed(f"Extended ping to {destination} failed with error: {e}")
        except Exception as e:
            logger.error(f"Unexpected error during extended ping: {e}")
            self.failed(f"Unexpected error during extended ping: {e}")
    
    def _perform_ping_test(self, destination, description):
        """Helper method to perform standard ping tests"""
        device = self.parameters['device']
        
        try:
            logger.info(f"Starting ping test to {destination} ({description})")
            result = device.ping(destination)
            logger.debug(f"Raw ping output: {result}")
            
        except SubCommandFailure as e:
            logger.error(f"Ping command failed: {e}")
            self.failed(f"Ping to {destination} ({description}) failed with error: {e}")
            return
        except Exception as e:
            logger.error(f"Unexpected error during ping: {e}")
            self.failed(f"Unexpected error during ping to {destination}: {e}")
            return

        # Display formatted output
        print(banner(f"Ping to {description} ({destination}):\n{result}"))
        
        # Parse and validate results
        success_match = re.search(r'Success rate is (\d+) percent', result)
        packet_match = re.search(r'(\d+)/(\d+) packets', result)
        
        if not success_match:
            logger.warning("Could not parse success rate from ping output")
            self.failed(f'Could not determine ping success rate for {destination}')
            return
            
        success_rate = int(success_match.group(1))
        
        # Additional packet loss analysis
        if packet_match:
            sent_packets = int(packet_match.group(2))
            received_packets = int(packet_match.group(1))
            packet_loss = ((sent_packets - received_packets) / sent_packets) * 100
            logger.info(f"Packet statistics: {received_packets}/{sent_packets} received ({packet_loss:.1f}% loss)")
        
        # Evaluate success criteria
        if success_rate == 0:
            self.failed(f'Ping to {destination} ({description}) completely failed - 0% success rate')
        elif success_rate < 80:
            logger.warning(f"Low success rate detected: {success_rate}%")
            self.failed(f'Ping to {destination} ({description}) had low success rate: {success_rate}%')
        elif success_rate < 100:
            logger.warning(f"Some packet loss detected: {success_rate}% success rate")
            self.passed(f'Ping to {destination} ({description}) succeeded with {success_rate}% success rate (some packet loss)')
        else:
            self.passed(f'Ping to {destination} ({description}) succeeded with {success_rate}% success rate')

class NetworkConnectivitySuite(aetest.Testcase):
    """Additional network connectivity tests"""
    
    @aetest.test
    def test_interface_status(self):
        """Verify critical interfaces are up"""
        device = self.parameters['device']
        
        try:
            # Get interface status
            parsed = device.parse('show ip interface brief')
            
            # Check for any interfaces that should be up
            critical_interfaces = []
            down_interfaces = []
            
            for intf, data in parsed['interface'].items():
                status = data.get('status', '').lower()
                protocol = data.get('protocol', '').lower()
                
                # Log interface status
                logger.info(f"Interface {intf}: Status={status}, Protocol={protocol}")
                
                # Identify potentially critical interfaces (adjust logic as needed)
                if any(prefix in intf.lower() for prefix in ['gigabit', 'ethernet', 'vlan']):
                    critical_interfaces.append(intf)
                    if status != 'up' or protocol != 'up':
                        down_interfaces.append(f"{intf} ({status}/{protocol})")
            
            if down_interfaces:
                logger.warning(f"Critical interfaces are down: {down_interfaces}")
                self.failed(f"Critical interfaces are down: {', '.join(down_interfaces)}")
            else:
                self.passed(f"All critical interfaces are operational ({len(critical_interfaces)} checked)")
                
        except Exception as e:
            logger.error(f"Failed to check interface status: {e}")
            self.failed(f"Could not verify interface status: {e}")

class CommonCleanup(aetest.CommonCleanup):
    @aetest.subsection
    def disconnect_device(self):
        """Clean disconnect from device"""
        device = self.parent.parameters.get('device')
        if device and device.connected:
            try:
                logger.info(f"Disconnecting from {device.name}")
                device.disconnect()
                logger.info("Successfully disconnected")
            except Exception as e:
                logger.warning(f"Error during disconnect: {e}")
        else:
            logger.info("No active device connection to clean up")

if __name__ == '__main__':
    import argparse
    from pyats.topology import loader
    
    # Set up argument parsing
    parser = argparse.ArgumentParser(description='Enhanced Network Connectivity Test Suite')
    parser.add_argument('--testbed', dest='testbed', type=loader.load, 
                       default='testbed.yml', help='Path to testbed file')
    parser.add_argument('--loglevel', choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'], 
                       default='INFO', help='Set logging level')
    
    args, unknown = parser.parse_known_args()
    
    # Configure logging level
    logging.basicConfig(level=getattr(logging, args.loglevel))
    
    # Run the test suite
    aetest.main(**vars(args))