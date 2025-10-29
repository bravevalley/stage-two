Given there are only two possibilites of the upstream pool. Rather than writing a complex shell script to dynamically swap the upstream servers at deployment, two sets of upstreams pool was declared as seen below.
```
upstream blue {
    server app_blue:3000          max_fails=1 fail_timeout=3s;
    server app_green:3000         backup;
}

upstream green {
    server app_green:3000         max_fails=1 fail_timeout=3s;
    server app_blue:3000          backup;
}
```
This way the arbitrary value of `ACTIVE_POOL` which could either be blue or green will be passed to `ngx_http_proxy_module.proxy_pass`. Although, this will not scale for larger deployment but its good enough for this use case; complexity beget complexity.