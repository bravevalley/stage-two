#!/usr/bin/env python3
"""
Blue/Green Deployment Log Watcher - COMPLETE FIXED VERSION
"""

import os
import re
import time
import json
from collections import deque
from datetime import datetime

# Import requests with error handling
try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    print("❌ requests library not available. Install with: pip install requests")
    REQUESTS_AVAILABLE = False

class LogWatcher:
    def __init__(self):
        self.slack_webhook = os.getenv('SLACK_WEBHOOK_URL')
        self.error_threshold = float(os.getenv('ERROR_RATE_THRESHOLD', 2))
        self.window_size = int(os.getenv('WINDOW_SIZE', 200))
        self.cooldown_sec = int(os.getenv('ALERT_COOLDOWN_SEC', 300))
        self.maintenance_mode = os.getenv('MAINTENANCE_MODE', 'false').lower() == 'true'
        
        # Debug counters
        self._debug_count = 0
        self._total_lines_processed = 0
        self._lines_with_pool = 0
        self._last_log_check = time.time()
        
        # Check if requests is available
        if not REQUESTS_AVAILABLE:
            print("❌ Cannot send Slack alerts - requests library not installed")
        
        # State tracking
        self.last_pool = None
        self.error_window = deque(maxlen=self.window_size)
        self.last_alert_time = {}
        self.current_pool = None
        
        # Log file path
        self.log_file = '/app/log/access.log'
        
        print("=" * 60)
        print("🔍 Blue/Green Log Watcher - COMPLETE FIXED VERSION")
        print("=" * 60)
        print(f"📊 Slack Webhook: {'✅ SET' if self.slack_webhook else '❌ NOT SET'}")
        print(f"📊 Error Threshold: {self.error_threshold}%")
        print(f"📊 Window Size: {self.window_size}")
        
        # Debug the log file immediately
        self.debug_log_file()

    def debug_log_file(self):
        """Debug information about the log file"""
        print(f"📁 Checking log file: {self.log_file}")
        print(f"   File exists: {os.path.exists(self.log_file)}")
        
        if os.path.exists(self.log_file):
            file_size = os.path.getsize(self.log_file)
            print(f"   File size: {file_size} bytes")
        
        # Check directory contents
        log_dir = '/var/log/nginx'
        if os.path.exists(log_dir):
            files = os.listdir(log_dir)
            print(f"   Files in {log_dir}: {files}")
        else:
            print(f"   ❌ Directory does not exist: {log_dir}")
        
        print("=" * 60)

    def wait_for_log_file(self, max_wait_time=60):
        """Wait for log file to be available and have content"""
        wait_start = time.time()
        
        print(f"⏳ Waiting for nginx logs (max {max_wait_time}s)...")
        
        while time.time() - wait_start < max_wait_time:
            if os.path.exists(self.log_file) and os.path.getsize(self.log_file) > 0:
                file_size = os.path.getsize(self.log_file)
                print(f"✅ Log file ready: {self.log_file} ({file_size} bytes)")
                return True
            
            elapsed = int(time.time() - wait_start)
            print(f"   Still waiting... ({elapsed}s/{max_wait_time}s)")
            time.sleep(5)
        
        print(f"❌ Log file not ready after {max_wait_time}s")
        return False

    def parse_log_line(self, line):
        """Parse Nginx log line and extract relevant fields"""
        self._total_lines_processed += 1
        
        # Print progress every 50 lines
        if self._total_lines_processed % 50 == 0:
            print(f"📈 Processed {self._total_lines_processed} lines, {self._lines_with_pool} with pool data")
        
        try:
            # Skip empty lines
            if not line.strip():
                return None
                
            # Enhanced regex patterns
            pool_match = re.search(r'pool="([^"]*)"', line)
            release_match = re.search(r'release="([^"]*)"', line)
            upstream_status_match = re.search(r'upstream_status=([\d-]+)', line)
            upstream_addr_match = re.search(r'upstream_addr=([^\s]+)', line)
            request_time_match = re.search(r'request_time=([\d.]+)', line)
            
            if not pool_match:
                return None
            
            self._lines_with_pool += 1
            
            log_data = {
                'pool': pool_match.group(1),
                'release': release_match.group(1) if release_match else 'unknown',
                'upstream_status': upstream_status_match.group(1) if upstream_status_match else None,
                'upstream_addr': upstream_addr_match.group(1) if upstream_addr_match else None,
                'request_time': float(request_time_match.group(1)) if request_time_match else 0,
                'timestamp': datetime.now().isoformat(),
                'raw_line': line.strip()
            }
            
            # Debug first few successful parses
            if self._lines_with_pool <= 3:
                print(f"✅ Parsed: pool={log_data['pool']}, status={log_data['upstream_status']}")
            
            return log_data
            
        except Exception as e:
            print(f"❌ Error parsing log line: {e}")
            return None

    def check_failover(self, log_data):
        """Check if a failover has occurred"""
        if not log_data['pool'] or log_data['pool'] == 'unknown':
            return False
            
        if self.last_pool and self.last_pool != log_data['pool']:
            failover_event = {
                'from_pool': self.last_pool,
                'to_pool': log_data['pool'],
                'timestamp': log_data['timestamp'],
                'type': 'failover'
            }
            
            print("🎯" * 20)
            print(f"🚨 FAILOVER DETECTED: {self.last_pool} → {log_data['pool']}")
            print(f"   Time: {log_data['timestamp']}")
            print("🎯" * 20)
            
            self.last_pool = log_data['pool']
            return failover_event
        
        # Track current pool for monitoring
        if log_data['pool'] != self.current_pool:
            self.current_pool = log_data['pool']
            print(f"📊 Current active pool: {self.current_pool}")
        
        self.last_pool = log_data['pool']
        return False

    def check_error_rate(self, log_data):
        """Check if error rate exceeds threshold"""
        if not log_data['upstream_status']:
            return False
            
        # Count 5xx errors
        is_error = log_data['upstream_status'].startswith('5')
        self.error_window.append(is_error)
        
        current_window_size = len(self.error_window)
        
        if current_window_size < self.window_size:
            return False
            
        error_count = sum(self.error_window)
        error_rate = (error_count / current_window_size) * 100
        
        if error_rate > self.error_threshold:
            error_alert = {
                'error_rate': round(error_rate, 2),
                'threshold': self.error_threshold,
                'window_size': current_window_size,
                'error_count': error_count,
                'timestamp': log_data['timestamp'],
                'type': 'high_error_rate'
            }
            
            print("⚠️" * 20)
            print(f"📈 HIGH ERROR RATE: {error_rate:.1f}% (threshold: {self.error_threshold}%)")
            print(f"   Errors: {error_count}/{current_window_size}")
            print("⚠️" * 20)
            
            return error_alert
        
        return False

    def can_send_alert(self, alert_type):
        """Check if we can send alert (cooldown period)"""
        now = time.time()
        last_time = self.last_alert_time.get(alert_type, 0)
        time_since_last = now - last_time
        
        if time_since_last < self.cooldown_sec:
            remaining = self.cooldown_sec - time_since_last
            print(f"⏰ Alert cooldown: {remaining:.0f}s remaining for {alert_type}")
            return False
            
        self.last_alert_time[alert_type] = now
        return True

    def send_slack_alert(self, alert_data):
        """Send alert to Slack"""
        if not self.slack_webhook:
            print(f"📝 Slack webhook not configured. Would send: {alert_data['type']}")
            return False
            
        if self.maintenance_mode:
            print(f"🔧 Maintenance mode active. Suppressing: {alert_data['type']}")
            return False
            
        if not REQUESTS_AVAILABLE:
            print(f"❌ Cannot send alert - requests library not available")
            return False
            
        if not self.can_send_alert(alert_data['type']):
            return False

        try:
            if alert_data['type'] == 'failover':
                message = {
                    "text": f"🔄 System Failover Alert: {alert_data['from_pool']} → {alert_data['to_pool']} | Time: {alert_data['timestamp']}",
                    "blocks": [
                        {
                            "type": "header",
                            "text": {"type": "plain_text", "text": "🔄 Blue/Green Deployment Failover Alert", "emoji": True}
                        },
                        {
                            "type": "section",
                            "text": {"type": "mrkdwn", "text": "Failover detected. Kindly check."}
                        },
                        {
                            "type": "divider"
                        },
                        {
                            "type": "section",
                            "fields": [
                                {"type": "mrkdwn", "text": f"*Previous Pool:* `{alert_data['from_pool']}` 🔵"},
                                {"type": "mrkdwn", "text": f"*Current Pool:* `{alert_data['to_pool']}` 🟢"}
                            ]
                        },
                        {
                            "type": "section",
                            "fields": [
                                {"type": "mrkdwn", "text": f"*Timestamp:* {alert_data['timestamp']} 🕐"},
                                {"type": "mrkdwn", "text": f"*Total Requests:* {self._total_lines_processed:,} 📊"}
                            ]
                        }
                    ]
                }
                print(f"📤 Sending failover alert: {alert_data['from_pool']} → {alert_data['to_pool']}")
                
            else:  # high_error_rate
                message = {
                    "text": f"🚨 Critical Alert: Error Rate at {alert_data['error_rate']}% | Time: {alert_data['timestamp']}",
                    "blocks": [
                        {
                            "type": "header",
                            "text": {"type": "plain_text", "text": "🚨 High Error Rate Alert", "emoji": True}
                        },
                        {
                            "type": "section",
                            "text": {"type": "mrkdwn", "text": f"The system is experiencing an elevated error rate above the configured threshold."}
                        },
                        {
                            "type": "divider"
                        },
                        {
                            "type": "section",
                            "fields": [
                                {"type": "mrkdwn", "text": f"*Current Rate:* {alert_data['error_rate']}% 📈"},
                                {"type": "mrkdwn", "text": f"*Threshold:* {alert_data['threshold']}% ⚠️"}
                            ]
                        },
                        {
                            "type": "section",
                            "fields": [
                                {"type": "mrkdwn", "text": f"*Error Count:* {alert_data['error_count']}/{alert_data['window_size']} ❌"},
                                {"type": "mrkdwn", "text": f"*Timestamp:* {alert_data['timestamp']} 🕐"}
                            ]
                        }
                    ]
                }
                print(f"📤 Sending error rate alert: {alert_data['error_rate']}%")

            print(f"🌐 Sending to Slack...")
            response = requests.post(
                self.slack_webhook,
                json=message,
                headers={'Content-Type': 'application/json'},
                timeout=10
            )
            
            if response.status_code == 200:
                print(f"✅ Alert sent successfully to Slack!")
                return True
            else:
                print(f"❌ Failed to send Slack alert. Status: {response.status_code}")
                return False
                
        except Exception as e:
            print(f"❌ Error sending Slack alert: {str(e)}")
            return False

    def watch_logs(self):
        """Main loop to watch and process logs"""
        print(f"🔍 Starting to watch log file: {self.log_file}")
        
        # Wait for log file to be available
        if not self.wait_for_log_file():
            print("❌ Cannot start without log file. Will retry...")
            time.sleep(10)
            return False
        
        print("🎯 Starting real-time log monitoring...")
        print("-" * 60)
        
        try:
            with open(self.log_file, 'r') as file:
                # Start from current end of file
                file.seek(0, 2)
                
                while True:
                    line = file.readline()
                    if not line:
                        time.sleep(0.1)
                        continue
                    
                    # Parse log line
                    log_data = self.parse_log_line(line)
                    if not log_data:
                        continue
                    
                    # Check for failover
                    failover_alert = self.check_failover(log_data)
                    if failover_alert:
                        self.send_slack_alert(failover_alert)
                    
                    # Check error rate
                    if log_data['upstream_status']:
                        error_alert = self.check_error_rate(log_data)
                        if error_alert:
                            self.send_slack_alert(error_alert)
                    
                    # Print status every 30 seconds
                    current_time = time.time()
                    if current_time - self._last_log_check > 30:
                        print(f"📈 Status: {self._total_lines_processed} lines processed, current pool: {self.current_pool}")
                        self._last_log_check = current_time
                        
        except Exception as e:
            print(f"💥 Error in watch_logs: {e}")
            raise
        
        return True

def main():
    """Main entry point with restart logic"""
    print("🚀 Starting Blue/Green Log Watcher - COMPLETE VERSION")
    
    watcher = LogWatcher()
    
    # Keep trying until successful
    while True:
        try:
            success = watcher.watch_logs()
            if not success:
                print("🔄 Restarting watcher in 10 seconds...")
                time.sleep(10)
        except KeyboardInterrupt:
            print("\n🛑 Stopping log watcher...")
            break
        except Exception as e:
            print(f"💥 Error: {e}")
            print("🔄 Restarting in 10 seconds...")
            time.sleep(10)

if __name__ == '__main__':
    main()