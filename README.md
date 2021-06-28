# auto-render
A automatic html render system.

This system uses a master api process, you can submit html remplates and then render them accordingly. Data is returned as a base64 encoded image.

## Installing and Running
1) - `git clone https://github.com/Crunchy-Bot/auto-render.git`
2) - `cd auto-render`
3) - `docker-compose build`
4) - `docker-compose up --scale worker=8 --detach`

You can view the api details at `http://127.0.0.1:8000`

## Env Vars
The system requires both `LUST_ADMIN_HOST` and `LUST_HOST` for submitting renders to [lust](https://github.com/chillfish8/lust)
