# Deploying redwoodcityweather

## Server setup
* Ubuntu 20
    * Digital Ocean shared server - 1GB 1CPU 25GB SSD
    * Change ssh port in `/etc/ssh/sshd_config`
    * Setup firewall - `ufw allow 8294/tcp`, `ufw enable`
    * Add user - `adduser ben` `usermod -aG sudo ben`
     
* Mysql 8
    * Login as root - `sudo mysql`
    * `create schema wx;`
    * Add `svc` user
    * Grant - `grant all on wx.* to svc@localhost with grant option;`

* Nginx - Follow DO tutorial (install, add to ufw, add domain in config)
    
* SSL cert - Follow DO tutorial


## Backend deploy (Flask app)
* TODO

## Frontend deploy (React app)
* TODO