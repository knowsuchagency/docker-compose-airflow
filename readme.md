# Airflow

This is meant as a template for getting up-and running with
apache airflow quickly using docker compose for local development
and docker swarm on Google Cloud for deployment.

What this is meant to do is help you establish a baseline deployment/development
environment with sane defaults.

There are many things that could be improved, but this should get you
up-and-running quickly with some good patterns.

## Some of the features
* [invoke] for orchestration and configuration
* [traefik] as edge proxy
* [grafana] as a metrics front-end for your cluster
* `pip install`able `flow_toolz` package for library code
* a recipe for creating new dags that can easily be extended `inv new-dag`


# Requirements

* docker `brew cask install docker-edge`
* python3 `brew install python`

## Quickstart
```bash
# create a virtual environment
python3 -m venv venv
# activate virtual environment
. venv/bin/activate
# install the flow_toolz package
pip install 'airflow/[dev]'
# generate self-signed tls cert and other filestubs
inv bootstrap
# bring up the server for local development
docker-compose up
```

# Authentication


You'll need to create two files at the project root for the purposes of authentication.
**They can be empty at first**, just to get the server running,
since docker-compose will expect them to exist.

* `aws-credentials.ini`
* `default-service-account.json`

## AWS

`aws-credentials.ini`
```.ini
[default]
aws_access_key_id = <your access key>
aws_secret_access_key = <your secret key>
```

## GCP
`default-service-account.json`

The `default-service-account.json` [service account key] at the project root will be used
to authenticate with Google cloud by default.

---

## TLS

In the [reverse-proxy](./reverse-proxy) folder, you will need 
a `certificate.crt` and `key.key` file that you can generate
with the `inv create-certificate` command.

This is really here just to get you started, you'll want to configure
traefik to use [letsencrypt] or other means to establish HTTPS on your 
production deployment.

## Other

For other string-based secrets, you'll need a `.secrets.env`[./airflow/.secrets.env] i.e.:
```
AIRFLOW_CONN_POSTGRES_MASTER={{password}}
```

In general:

Authentication **strings** should be a [the secrets file](./airflow/.secrets.env)

Authentication **files** should be set as a docker secret in the [docker compose file](docker-compose.yaml)

Secrets SHOULD NOT be checked into version control.

# Local Development

Initialize the development server (once you have the authentication files described earlier)

``docker-compose up``

Note: it may take some time for the docker images to build at first

The airflow ui will now render to [localhost](localhost:80)

The reverse proxy admin panel will be at [localhost:8080](localhost:8080)

Grafana dashboard will be at [localhost:3000](localhost:3000)
```
user: admin
pw: admin
```

DAGs, and libraries in the [airflow](airflow) folder will automatically
be mounted onto the the services on your local deployment and updated on 
the running containers in real-time.

## Writing a new DAG

There exists a [handy dag template](airflow/flow_toolz/templates/dag_template.py.jinja2)
for new dags.

You can use this template to quickly write new dags by using the [task runner](tasks.py):
```bash
# invoke the new-dag task
# you will be prompted to provide parameters 
# such as `dag_id` and `owner`
inv new-dag
```

# Library Code

In the [airflow](./airflow) folder, there is a [flow_toolz](airflow/flow_toolz) directory.
That directory is a Python package, meaning it can be `pip install`ed.

Code that is shared between dags, or that you want to use outside of airflow (for testing/development) purposes
should be put there.

```
. venv/bin/activate

pip install -e './airflow'

# in python, I can now

import flow_toolz
...

```

# Configuration

The infrastructure -- services and how they'll communicate --
are all described in `docker-compose.yaml`

Cross-service configuration -- environment variables that will exist across different services/machines -- 
will be in either a `.env` file or `.secrets.env` -- the latter for sensitive information that
should not exist in version control.

You'll notice some of these environment variables follow the pattern `AIRFLOW__{foo}__{bar}`.

That tells airflow to configure itself with those variables as opposed to their analog in its default config file.
More information on how Airflow reads configuration can be found [at this link](https://airflow.apache.org/howto/set-config.html)

For configuration related to automated cli tasks [executed via invoke](http://www.pyinvoke.org/),
those are in `invoke.yaml` files and can be overridden by environment variables as well.
For more information on how `invoke` configuration works, [follow this link](http://docs.pyinvoke.org/en/0.11.1/concepts/configuration.html).

# Deployment

### Create the swarm (spins up machines on GCP)
```bash
inv swarm-up
```

### Deploy to our swarm
```bash
inv deploy --prod
```

## Notes

* you'll want to change the names of the images in the docker-compose file for your own deployment
* invoke tasks that make use of google cloud i.e. `inv deploy` will expect
a `project` element in the configuration. I have this set in my `/etc/invoke.yaml`

Here's an example:
```yaml
gcp:
  project: myproject
```

You'll likely also want to change your default host bind **ip** in Docker for Mac

![Imgur](https://i.imgur.com/Vu8vgqA.png)

[invoke]:http://www.pyinvoke.org/
[traefik]:https://traefik.io/
[grafana]:https://grafana.com/
[letsencrypt]:https://letsencrypt.org/
[service account key]:https://cloud.google.com/iam/docs/creating-managing-service-account-keys
