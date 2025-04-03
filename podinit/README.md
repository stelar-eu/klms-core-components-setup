# The podinit container image

This container image is used by the __podinit.libsonnet__ library klms-deploy repository. The image is
targeted to be used by Kubernetes initContainers, for the purpose of enabling the
startup of services which depend on other services.

For this purpose, the container supports the __wait4x__ utility, found in
[https://wait4x.dev/](https://wait4x.dev/). Please consult this page for documentation
of wait4x, along with the podinit library.

Note that kubernetes purists frown upon waiting for initialization; they prefer to fail and restart!
