LSF Community Edition for the tutorial can be downloaded from the following links:

* x86_64 processor (amd64) - [Provide URL the day of tutorial]
* Apple silicon (arm64) - [Provide URL the day of tutorial]

The x86_64 processor LSF should be placed in the current directory with the name `lsfsce10.2.0.15-x86_64.tar.Z`. The Apple silicon LSF should be placed in the current directory with the name `lsfsce10.2.0.15-armv8.tar.Z`. We recommend using a tool such as wget as follows:

* `wget -L -O lsfsce10.2.0.15-x86_64.tar.Z [URL from above]`
* `wget -L -O lsfsce10.2.0.15-armv8.tar.Z [URL from above]`

If the URL is a Box share link (`https://ibm.box.com/s/<id>`), `wget` saves the Box web page instead of the archive. Use the direct-download form `https://ibm.box.com/shared/static/<id>` instead, and check the result with `gzip -t <archive>`.
