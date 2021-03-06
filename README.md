Dibctl
------

Dibctl is a software for image lifecycle management.
It helps to build, test, upload and delete images in multipie
openstack regions in a consitent way.

Internally it uses diskimage-builder to build images and pytest
with testinfra to test them.

Dibctl uses configuration files to describe how to build image,
which name it should have after upload, what properties (if any)
should be set for a given image. Image configuration file also
provide list of tests for each image, plus name of environment
where tests should happen.

Testing happens under directives from `test.yaml`. It contains
information how to run a test instance: region authorization URL,
credentials, flavor, network list, availability zone, security
groups and other nova parameters.

Third configuration file (`upload.yaml`) provides information
for uploading that image into Openstack installations.

Image Lifecycle
---------------
Dibctl assumes following image lifecycle:
- Image developed and debugged by operator using command line
  interface.
- Resulting configuration is used in CI server to build image
- Newly build image is then tested
- If tests passed image is uploaded to one or more regions
- During upload process older copies of image are marked as obsolete
- Obosolete images which are no longer in use deleted

Steps "build, test, upload, obsolete, delete" repeated on
periodic basis.

Testing frameworks
------------------
Dibctl provides few frameworks for image testing.
Each of those frameworks provides tests with full information
about image,it properties, created instance (it flavor, network
settings, credentials to access instance SSH, etc).
Test frameworks:
- 'shell': each test is a simple shell script, which is executed
outside test VM. It is provided with all information on how
to connect to the test VM.
- 'pytest' - tests are implemented by means of py.test, with optional
support for testinfra (python library for server verification, similar to
ServerSpec). Dibctl provides vast set of fixture containing all available
information about the image and the instance, plus few handy operations
(wait\_for\_port), and a direct access to 'nova' object of openstack
client for testing instance reactions on nova operations
(hard reboot, rebuild, etc).
- 'ssh': each test is a simple shell script, which is executed
inside a guest machine (not yet implemented)
- 'image': passive check of the image content (not implemented yet)

Dibctl comes with some generic tests (which should be applicable
to any image of any provider).

Few examples:
- Does instance resize rootfs up to a flavor size at a first boot?
- Does it receive settings and configure IP addresses on all attached interfaces?
- Does DNS resolver set up properly?
- Does hostname match the name of the instance?
- Does instance work after reboot?
- Can user install nginx and get access to http port 80?

Workflow in details
-------------------
After operators describes configurations, following workflow excepted:
- build: create new image py means of diskimage-builder
- test: new instance is spawned from image under test, and corresponding
  tests are called. If they all report success, images passes the test.
- upload: If test was successful, the image is uploaded to to one or more
  installations of Openstack.
- Older copies of images marked as obsolete and removed (after they become
  unsed - see description below).

That process may be repeated on regular basis via cron or CI server (Jenkins?).
Comprehensive testing assures that image that passed the test may be uploaded
safely in automated manner.

At the same time dibctl may be used by operators from command line and it
provides some means of interfactive debug of faulty images:
- `--shell` option allow to open shell to instance which failed some tests
- `--keep-failed-instance` allow to keep instance alive (normally it should
  be deleted at the end of the test)
- `shell` command allow open shell without running any tests.

Motivational introduction
-------------------------

Diskimage-builder solved most of the issues around process of building images.
It reduces all complexity of images to set of elements and well-defined rules
of the build process.
Nevertheless, there are many problems outside of the diskimage-builder scope:

- Integration testing
- Linking together diskimage-builder-related information (environment variables,
  command line options) and glance-related information (image name, properties
  credentials for upload, etc)
- Unified upload to one or more regions
- Recycling of older image copies

Let's look to all those sages. Firstly, one need to set up:

- environment variables for diskimage-builder
- few very inconsistent and cryptic variables for used elements
- some command line arguments for diksimage-builder
- list of elements used to build an image

Resulting command line is a 'golden artifact' - you need to keep it
somewhere.

After the image was build, one can upload it to Glance. One need
to provide few more pieces of information:
- Image name
- Credentials for Glance
- Additional meta needed to set up on image (`hw_property`, etc)

This adds few more lines to the 'golden artifact'.

Normally one wants to test images before uploading. Each image should, at least,
be able to boot and accept ssh key.

One may create a simple script to boot and test it:

This adds few more lines to 'golden artifact':
- credential to spawn instance
- flavor id
- nics net-id
- security group name

If one have more than one image with more than one configuration
for testing, this brings up complexity even higher, as many of those
values become variables for reusable part of the script.
If tests failed one should not leave broken and forgotten instances,
ssh keypairs and test images. So there should be garbage collection
code or some kind of 'finally' clause in the script.

After upload one want to remove older copies of the same image.
That adds even more lines to the script, bringing it to the scale of
a normal application.

Dibctl was created as evolution of such script, which at certain
point become unmanageable. Newer version was written with better understanding
of the process, without cutting corners.


Outside of its main goal, dibctl gives one more nice feature: image-transfer,
which can copy image from one glance to another while preserving every propery,
ownership and share information (tenant-name based).

Key concepts
------------

Dibctl uses following concepts:
- *label* (for image and environment) - internal 'name' for a given image or environment to
  use in command line and in cross-reference fields.
  All entries in dibctl configuration have label, or 'namelabel'.
- *image*: set of attirbutes to build and test actual image.
- *test instance*: Instance which is used for image testing. Test instance is created
  at test time and   removed afterwards. Dibctl creates custom SSH key for each test.
- test image: image which is uploaded for testing. Dibctl uses separate upload stage
  for testing and actual 'upload to procution'. Test images normally uploaded to specific
  project and are not public. Production images are normally public (or upload to
  selected tenant and shared  with specific tenants). Test image is removed after test
  (succesfull or not). This can be changed by --keep-failed-image option.
- test environment: set of attributes and variables describing how upload test image and
  how to boot test instance. Every image references to test environement by it's label.
  They are listed in tests.yaml
- upload environments: Those describe how and where upload images for production use.
  Uploaded images are subjected to optional 'obsoletion' stage (see Obsoletion part below),
  which happens automatically every time image is uploaded or manually.


Image lifecycle
---------------

Any of those stages is optional an may be ommited.

## Build stage
It uses information from corresponding entry in images.yaml to execute diskimage-builder.
'filename' option specify target filename.
dibctl translates diskimage-builder exit codes
(it exits with same exit code as diskimage-builder).

## Test stage
At this stage image should be build. Dibctl uses information from entry in images.yaml
to find image file for testing ('filename'), and than uses `environment_name` to
find correspoinding test environment in tests.yaml. Then it upload image, creates new ssh key,
spawns instance accoring to test environments settings, and executing tests
in `tests_list` section of image configuration. Those tests recieve information about
instance (IP addresses, network settings, hostname, flavor, etc), perform instance validation.
If all tests passes successfully, dibctl sets exit code to 0, otherwise error returned.
Regardless of the test results all test-time objects in Openstack are removed: test image,
test instance, ssh key. User may use `--keep-failed-image` and `--keep-failed-instance` to
keep them for closer investigation.

By using --shell dibctl may be instructed to open ssh shell to test machine when tests failed.
After that shell is closed, instance (and all other pieces of test) are removed.
If operator wants to keep instance from been removed after shell is closed, he (she) may
use 'exit 42' command. Dibctl will honor exit code 42 by not removing instance.


## Upload stage
At the upload stage image is uploaded to specified installation with specific settings
for publication. All image-specific things (properties, tags, etc) from images.yaml
are used during this stage, as well, as settings from upload.yaml (See variable ordering
to see override rules).

After upload done, it triggers *obosoletion stage* if obsoletion is stated in
upload configuration.

## Obsolete stage
Obsolete image: If image is in the same tenant and have same glance name as freshly uploaded,
it is obsolete. Obsoleted images recieve specific rename pattern (usually adds 'Obsolete ' before
name), and specific set of properties.

Obsoletion may be performed manually by 'obsolete' command.

## Rotation stage
If obsolete image is no longer used by any instances in installation it's called 'unused obsoleted
image' and may be safely removed. That is done by 'rotate' command.

Please note, rotation requires administrative privilege (dibctl needs to see all instances
in the region). Normally it's performed periodically by administrator itself, without
delegating this job to CI/cron.

Installation
------------
You need to have following packages installed:
- diskimage-builder
- novaclient
- glanceclient
- keystoneauth1

Important notice: at this moment diskimage-builder package in Debian & Ubuntu is very,
very old (1.0). You need to upgrade it al least to 1.9 to have working images.

Please use pip version or rebuild package if you have own CI/buildfarm.

If you want to use python-based test you will also need:
- pytest
- pytest-timeout
- pytest-testinfra (it's new library and it may not be in your distro yet, use pip
or build your onw package).

Note: Due to bug [1] Ubuntu Xenial's bug, you may recieve pytest warnings when
using pytest runner. Ubuntu's python-pytest-timeout package is obsolete.
Those warnings are harmless, but if you want to get rid of them, upgrade
python-pytest-timeout package to the newer one.

[1] https://bugs.launchpad.net/ubuntu/+source/python-pytest-timeout/+bug/1676301

TODO: set up ppa with dependencies

Configuration
-------------

Every configration file is consists of independent entities. When dibctl scans
for configuration it works with all possible configuration file locations
in a spefic order. Every found configuration file is merged into
common configuration (separately for each type). If configuration file
with higher priority has entity with same label as in files with less
priority, it is replaced with newer entity, and warning is logged to
console.

There are 3 places where configuration are searched: local directory,
'dibctl' calalog in current directory and '/etc/dibctl'.

There are 2 types of configuration files: monolythic and 'conf.d' style.
Files from '.d' catalogs are loaded in alphabetical order.
All together that gives 6 different configuration file locations for
earch configuration type.

There are three different types of configuration files: images (`images.yaml`),
test environments (`test.yaml`) and uploads (`upload.yaml`)

### Lookup order for image configuration
(sorting is from the least priority to the highest priority)
- `/etc/dibctl/images.yaml`
- `/etc/dibctl/images.d/*.yaml`
- `./dibctl/images.yaml`
- `./dibctl/images.d/*.yaml`
- `./images.yaml`
- `./images.d/*.yaml`

### Lookup order for test environment configuration
(sorting is from the least priority to the highest priority)
- `/etc/dibctl/test.yaml`
- `/etc/dibctl/test.d/*.yaml`
- `./dibctl/test.yaml`
- `./dibctl/test.d/*.yaml`
- `./test.yaml`
- `./test.d/*.yaml`

### Lookup order for upload environment configuration
(sorting is from the least priority to the highest priority)
- `/etc/dibctl/upload.yaml`
- `/etc/dibctl/upload.d/*.yaml`
- `./dibctl/upload.yaml`
- `./dibctl/upload.d/*.yaml`
- `./upload.yaml`
- `./upload.d/*.yaml`


If pytest-based tests are in use, than tox.ini and other pytest-related
configuration files may influence tests discovery.

### `images.yaml`
This file describes how to build image, which name and properties it
should have in Glance during upload, which *test_environment* to use
to test this image, which tests should be ran during test stage.

### `test.yaml`
This file describes test environments. They may be referenced by
images in `image.yaml`, or forced to be used during test from
command line.
It contains all openstack information for test
purposes:
- Where to upload image for test (OS credentials)
  (images are upload for test independently from
   actual 'upload' stage)
- Which flavor, network(s), etc to use

### `upload.yaml`
This file contains configuration for upload.


Variable override ordering
--------------------------
When dibctl performs tests or uploads it combines
information from `images.yaml` and correspoding
environment config (`test.yaml` or `upload.yaml`).

Each of that file may contains `glance` section.
Normally all image-specific variables should
be kept in the `images.yaml` config file,
but under certain circumstances it may be desirable
to override/change them for a given location.
Most noticable and common are timeout settings
(for remote/slow regions) and `glance_endpoint`
to help deal with complicated intra-extra-net
endpoints.

Special priority rules for `glance` section:
- `api_version` - environment have priority over image
- `upload_timeout` - used a max of all available values
- `properties` - merged. If there are same properties in
   the images config and in environement config,
   environments have priority over image.
- `tags` - merged (this is a simple list)
- `endpoint` - environment have priority over image
- `protected` - max of all values (True > False)
- `min_disk` - max of all values
- `min_ram` - max of all values
- all timeout values: max of all values

For all other variables image has priority over environment.

There are examples of configuration files in
`docs/example_configs/` folder of this repository.

Writing a test
==============

General conceptions for good py.test test are applied:
- each test checks only one thing
- use assert/raise to signal errors

* `dibctl build imagelabel [-o filename] [--images-config images.yaml]`
  Build given image

* `dibctl test imagelabel [-i filename] [--images-config images.yaml] [--test-environments-config env.yaml] [--upload-only] [--use-existing-image uuid] [--force-test-env env-name]`

Upload image to test tenant and spawn instance, run tests against this instance. Return -1 if test failed, or 0 if tests passed.
If no filename supplied, 'filename' form images.yaml is used. os\_tenant\_name, os\_password, os\_auth\_url, os\_username may
be overrided via environment variables, and may be ommited in config


* `dibctl upload imagelabel [-i filename] [--images-config images.yaml] [--no-obsolete]`

Upload image to a given environment with properties and name from images.yaml
Old images with same name (in the same tenant) would be renamed to 'Obsolete (oldname)' and marked with property.

* `dibctl mark-obsolete uuid [uuid, ...]`
Obsolete given image name (rename and mark it with property)

* `dibctl rotate ["Image Name 1" "Image Name 2" ...]`

Rotate (remove) unused obsolete images with given name (if no name given, all unused obsolete images are processed)
Requires administrative permissions to find if image is unused or not.


Dibctl uses environment variables for Openstack credentials (except for the tests where it uses credentials from test-environments.yaml).
It uses standard names for environment variables:
```
OS_USERNAME
OS_PASSWORD
OS_TENANT_NAME
OS_AUTH_URL
```

For test command dibctl prioritize environment configuration with exception of OS_PASSWORD,
which have higher priority over configuration file.

Exit codes
----------
When everything went well, exit code is 0.
If there is an error with configuration file, or connection error, exit code is -1
If diskimage-builder failed, exit code is the same as disk-image-create's exit code
If there were test or upload error, exit code is positive (not implemented yet)


Timeouts
--------

For most of operations Dibctl have a time limit. Those timeouts have reasonable
default values, but it's possible to override them. When the same timeout is
specified in two configuration files, dibctl uses maximal value.
For example, if image config  in glance section has `upload_timeout: 300`, and
environment has `upload_timeout: 3600`, Dibctl will wait up to 3600 seconds during
image upload.

All time-related settings for Dibctl are measured in seconds.

List of timeout settings (default value is provided in braces):
- `glance.upload_timeout` (360 seconds). Limit how long image may be uploaded.
  Applied to test, upload and transfer commands.
  All operations stops if this timeout was triggered. Glance image would
  be left half-uploaded, and, hopefully, would be cleaned by glance.
  May be specified in images.yaml, test.yaml and upload.yaml configs.
- `tests.wait_for_port` (61 seconds). Limit how long to wait instance between
  become ACTIVE and answering on a `wait_for_port` port. Applied to test
  command only.
  May be specified in images.yaml and test.yaml configs.
- `nova.create_timeout` (10 seconds): Limit how long nova may answer to
  instance creation request.  It does not include time for transfer from
   'created' to 'BUILD' and 'ACTIVE' states, only the actual 'create' command.
  Applied only to test command.
  May be specified in images.yaml and test.yaml configs.
  If this timeout was triggered, uploaded image would be removed, keypair
  will be removed and instance would be left 'as is'.
  All further operations would be stopped.
- `nova.active_timeout` (360 seconds). Limit how long dibctl will wait
   for instance after it was created before it become 'ACTIVE' (or fall
   into 'ERROR' state).
  May be specified in images.yaml, test.yaml and upload.yaml configs
  Applied to test command only.
  If this timeout was triggered tests would not be called.
  Further operations are dependent on command line options:
  image will be removed unless there are --keep-failed-image option.
  instance will be removed unless there are --keep-failed-instance option.
  keypair will be removed anyway, but private key in filesystem would be
  kept in instance was kept.
- `nova.keypair_timeout` (10 seconds). Timeout for keypair operations.
   Normally you wouldn't need to change this.
   May be specified in images.yaml, test.yaml
   Applicable to test command only.
   If this timeout was trigged, image would be removed, keypair left
   as is, all further operations would be stopped.
- `cleanup_timeout` - not yet implemented.
  Applied to test command only
  May be specified in images.yaml, test.yaml
- Each element in tests.tests\_list has own `timeout` value, which
  is limiting time for all tests gathered under given path combined.
  For example, if you have test like this:
  ```
  tests:
    tests_list:
      - pytest: /foobar.py
        timeout: 300
 ```
 Than if foobar.py contains 3 tests each finishing in 120 seconds,
 than timeout would be triggered at the third test, at 300th second.
 May be specified only images.yaml
 Applied only to test command.
 If this timeout was triggered, behavior is dependent on
 --keep-failed-image, --keep-failed-instance
 and --continue-on-fail option. Regardless of those options,
 rest of tests under given line (which triggered timeout)
 would be skipped (This is due to the test process terminated abruptly).
 After failure or successful operation there is a cleanup stage.
 Each operation in this stage uses same `cleanup_timeout` value.
 If one operation is triggered timeout, dibctl will continue to perform
 next operation in cleanup cycle.

 If by any reason you want to stop dibctl to perform cleanup cycle
 after you ran it, you may at your choice:
 - use kill -9 to it
 - press Ctrl-Z and than `kill -9 %1` (everywhere except for opened shell)
 - use `exit 42` in the opened shell to disable cleanup sequence (works
   only inside shell due to obvious reasons).

Pressing Ctrl-C during all operations will threated as failure and would
cause clean sequence accordingly to the command line settings.

Timeout sequence:

- upload\_image: wait up to `glance.upload_timeout`
- create test keypair: wait up to `nova.keypair_timeout`
- spawn test instance: wait up to `nova.create_timeout`
- wait for instance to become ACTIVE: wait up to `nova.active_timeout`
- wait for instance to answer port: wait up to `tests.wait_for_ports`
- each entry from tests\_lists will be capped at it own timeout value.

After tests (or after failure, or after user exited a shell from instance
and that instance should be cleaned up due to command line settings)
Eeach clean operation will be capped up to cleanup\_timeout value.
If timeout happens

Individual tests may apply own time limits. For shell tests
it's normally done with 'timeout' command, for pytest-based
tests it is done with `pytest.mark.timeout` decorator.

Example for the test below has timeout value 15:

```
@pytest.mark.timeout(timeout=15)
def test_hostname(ssh_backend, instance):
    assert ssh_backend.SystemInfo.hostname == instance.name.lower()
```

Getting started
---------------
There are two distinct workflows you may follow:
- git-based CI/CD style (git style)
- system-wide configuration style (system config style)

### git style
In this mode all configuration files, tests and diskimage builder
elements are stored in a single git repository.

This example will operates on following assumptions:
* You already has installed dibctl system-wide (via pip install or
through apt-get)
* You repository will be called `images`.
* You have one images to build: Debian Jessie
* You have two installations to upload images: cloud-us and cloud-uk

Preparation:
- `mkdir images`
- `cd images`
- `git init`
- `mkdir dibctl`
- `mkdir tests`

Those commands will initialize new repository `images` with
catalogues `dibctl` (we will store dibctl configuration files here),
'tests' (where we'll store our tests there).


#### Configuration file for images
We will create it at `dibctl/images.yaml`:

```
debian:
  filename: debian.img.qcow2
  glance:
    name: "Automated Debian Image"
  dib:
    environment_variables:
      DIB_RELEASE: jessie
    elements:
      - debian
      - vm
  tests:
    ssh:
      username: debian
    wait_for_port: 22
    tests_list:
      - shell: tests/reboot.sh
      - pytest: tests/generic.py

```
Example above is a very short configuration file, there are
many options to tweak, check docs/example\_configs to see
all possible options.

Comments:

We use system-wide elements for diskimage-builder
here. If we want to use custom elements, we need to specify
environment variable ELEMENTS_PATH in section 'dib':
```
image-name
  dib:
    environment_variables:
      ELEMENTS_PATH: 'elements'
    elements:
      my-custom-element
```
In this case path may be relative (to the working catalog
of dibctl) or absolute path.

`ssh` section in tests specify settings for ssh - in our
case it's just a username.

`wait_for_port` specify which port to wait after instance
was created. Dibctl will wait (up to timeout, default is 61 seconds,
but can be overriden with `port_wait_timeout` option) for
given TCP port to start accepting connections (simple SYN/ACK test
without actual transmission of anything).

`tests_list` define which tests we want to run. Those tests will
be created in a section below. We are using two test frameworks:
- `shell` - shell scripts, which are executed outside of instnace
and have special set of variables providing information about
instance to test.

- `pytest` - execure pytest tests outside of of instance but
have special `ssh_backend` fixture which allows connection to
'inside' of guests.


#### Configuration file for test environment

### system-config
