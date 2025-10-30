# Blue/Green Deployment Runbook

## Overview
This runbook provides operational procedures for handling alerts and incidents in our Blue/Green deployment setup. Our system uses two identical environments (Blue and Green) to ensure zero-downtime deployments and quick recovery from failures.

## Alert Types

### 1. 🚨 Failover Detected Alert

#### Description
- **Severity**: High
- **Trigger**: Automatic traffic switch between pools (Blue→Green or Green→Blue)
- **Cause**: Primary pool health degradation or error responses
- **Impact**: Service continues but redundancy is reduced

#### Diagnostic Steps
1. **Check Pool Health Status**
   ```bash
   # Check Blue pool health
   curl http://localhost:8081/healthz
   
   # Check Green pool health
   curl http://localhost:8082/healthz
   ```

2. **Review Application Logs**
   ```bash
   # For Blue pool
   docker-compose logs app_blue --tail=100
   
   # For Green pool
   docker-compose logs app_green --tail=100
   ```

3. **System Health Check**
   - Monitor CPU and memory usage
   - Verify network connectivity
   - Check for system resource exhaustion

#### Recovery Procedure
1. **If Chaos Testing is Active**
   ```bash
   # Stop chaos testing
   curl -X POST http://localhost:8081/chaos/stop
   ```

2. **Recovery Monitoring**
   - Wait for automatic recovery (2-5 minutes)
   - Verify traffic routing returns to primary pool
   - Confirm service stability

### 2. ⚠️ High Error Rate Alert

#### Description
- **Severity**: Critical
- **Trigger**: >2% of requests returning 5xx errors (in last 200 requests)
- **Impact**: Active service degradation affecting user experience

#### Diagnostic Steps
1. **Monitor Current Error Rate**
   ```bash
   docker-compose logs alert_watcher | grep "High error rate"
   ```

2. **Analyze Application Logs**
   ```bash
   # Review recent Blue pool logs
   docker-compose logs app_blue --tail=20
   
   # Review recent Green pool logs
   docker-compose logs app_green --tail=20
   ```

3. **Check Nginx Error Logs**
   ```bash
   docker-compose exec nginx tail -100 /var/log/nginx/access.log | grep "upstream_status=5"
   ```

#### Recovery Procedure
1. **Immediate Actions**
   - [ ] Assess error patterns in logs
   - [ ] Verify database connectivity
   - [ ] Check external service dependencies
   - [ ] Monitor system resources

2. **If Errors Persist**
   - [ ] Initiate manual failover if necessary
   - [ ] Scale resources if resource constraints identified
   - [ ] Consider rolling back recent changes

3. **Recovery Validation**
   - [ ] Confirm error rate drops below threshold
   - [ ] Test critical service endpoints
   - [ ] Monitor application performance metrics
   - [ ] Verify user-facing functionality

