Deployment of  a Blue/Green Nodejs service behind Nginx using pre-built container images (no application code changes, no image rebuilds). This task involved routing, health-based failover, and automated verification via CI.

## How to run
1. Download the project
```
git clone https://github.com/bravevalley/stage-two.git
```
2. Change directory into the project folder
```
cd ./stage-two
```
3. Run docker-compose
```
docker-compose up -d