# sensorctl

Command line client for the [sensor-hub](https://github.com/bulbashenko/pet-devops) telemetry daemon.

```console
$ sensorctl status --endpoint http://localhost:8080
status : ok
version: 0.1.0

$ sensorctl stats -n 100
SENSOR              COUNT       MIN      MEAN       MAX    STDDEV
humidity-01           100    37.412    45.031    52.847     5.612
imu-01-accel-z        100     9.428     9.810    10.192     0.281
temp-01               100    18.601    21.498    24.394     2.105
```

The version is derived from the repository's git tag, so the wheel, the Conan
package, the `.deb` and the container image always carry the same version
string. See `docs/adr/0002-version-from-git-tag.md`.
