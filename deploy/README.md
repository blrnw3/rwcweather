# Deploying redwoodcityweather

## Server setup
* Ubuntu 20
    * Digital Ocean shared server - 1 GB RAM, 1 CPU, 25 GB SSD
    * Change ssh port in `/etc/ssh/sshd_config`
    * Setup firewall - `ufw allow 8294/tcp`, `ufw enable`
    * Add user - `adduser ben`, `usermod -aG sudo ben`
     
* Mysql 8
    * `sudo apt install mysql-server`
    * `sudo mysql_secure_installation`
    
    * Login as root - `sudo mysql`
    * `create schema wx;`
    * Add `svc` user
    * Grant - `grant all on wx.* to svc@localhost with grant option;`
    * Future access: `mysql -u svc -p`

* Nginx - Follow DO tutorial (install, add to ufw, add domain in config)
    * sites-available are in deploy/
    
* SSL cert - Follow DO tutorial


### Flask app setup
* [Tutorial for flask on nginx](https://www.digitalocean.com/community/tutorials/how-to-serve-flask-applications-with-uwsgi-and-nginx-on-ubuntu-20-04)
    * `python3.8 -m venv venv_prod` within ~/rwcweather and `source venv_prod/bin/activate` and `pip install -r requirements.txt`
    * Use files deploy/rwcwx.ini and .service


### Next.js setup
* https://www.digitalocean.com/community/tutorials/how-to-set-up-a-node-js-application-for-production-on-ubuntu-20-04
    * Skip step 2 and for pm2 start cmd, do `pm2 start npm --name "rwcwx-app" -- start` 

### Demon scripts
* Configure Cumulus to FTP to the server
    * Use SFTP so no FTP setup required (SSH settings can be used)
* For webcam setup, may actually need to setup an FTP server (DO tutorial)
    * Use config file: deploy/vsftpd.config
* Add deploy/crontab to ben user's crontab
* Within ~/rwcweather run `MYSQL_URL=svc:<PASS>@127.0.0.1:3306/wx PYTHONPATH=/home/ben/rwcweather nohup python3 rwcwx/job/save_latest.py -o /var/www/rwc/html/cumulus/realtime.txt -e out_prod  &>> log/get_latest.log &`
    * Change <PASS> to the prod password
    * TODO: make this into a system service so it does not need restarting on system reboot / code changes
* Setup cam_save.sh script to run
    * nohup ./cam_save.sh &> /dev/null &
    * TODO make a daemon

## Ongoing deployment
* Within web/app run `npm run build` to compile the web app (DO NOT do this on server - too slow)
* Sync all the code from outside root dir:
 `rsync -ruv -e 'ssh -p 8294 -i ~/.ssh/digitalocean_private_ben_centos_openssh' rwcweather ben@138.68.56.237:~/ --exclude=".git/" --exclude="venv/" --exclude="web/app/.next/cache" --exclude="web/app/node_modules/"`
* If requirements.txt has been updated, activate venv_prod and install them
* If package.json has been updated, run `npm install` from within web/app/
* On the server, run `sudo systemctl restart rwcwx` and `pm2 restart rwcwx-app`
* If updates to the save_latest script have been made:
    * Kill running process: ps -aux | grep python to find it
    * see 'demon scripts' for restart command
    
### Troubleshooting
* Node logs: `pm2 logs`
* Flask logs: `journalctl -u rwcwx --since today`
* Nginx access logs: `sudo tail -f /var/log/nginx/access.log`
    * Error log is at error.log
    
### Upgrading
* https://nextjs.org/docs/upgrading

    