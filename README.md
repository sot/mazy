# Mazy : fetch Chandra resource pages

The `mazy` command accepts an initial `resource` positional argument, followed by
optional positional tokens that are classified as obsid, AGASC ID, load
name, or date.

## Help
```
usage: mazy [-h] [--archive-only] [--print-url] [--local | --occweb] [--version] resource [args ...]

Resolve positional inputs as obsid, AGASC ID, load name, and/or date, then open the
selected content resource. Note that a date must be provided in a string format (float
CXC seconds are not accepted).

positional arguments:
  resource        Content resource name: starcheck, mica, agasc, star_history, centroid_dashboard, chaser
  args            Positional arguments: date, obsid, load_name, AGASC ID

options:
  -h, --help      show this help message and exit
  --archive-only  Use archive-only (flight scenario) for kadi commands
  --print-url     Print the URL that would be opened instead of opening it in a browser
  --version       show program's version number and exit

Content location (choose one, default=cxc/icxc):
  --local         Use local content
  --occweb        Use OCC web content
```

## Examples
```
mazy starcheck APR2924A --occweb
mazy mica 43474
mazy centroid_dashboard 2024:125:06:22:32 --local
mazy star_history 701368208
mazy agasc 701368208
mazy chaser 43474
```
