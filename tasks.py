from concurrent import futures
from functools import partial
from pprint import pprint
from pathlib import Path
import subprocess as sp
import itertools as it
import datetime as dt
import atexit
import os
import re

from importlib_resources import read_text

from invoke import task

from jinja2 import Template


shell = partial(sp.run, stdin=sp.PIPE, stdout=sp.PIPE, universal_newlines=True)


@task
def swarm_up(c):
    """
    Create a docker swarm on google cloud.
    """

    project = c.config.gcp.project
    zone = c.config.gcp.zone
    machine_type = c.config.gcp.machine_type
    managers = c.config.gcp.managers
    workers = c.config.gcp.workers

    machines_desired = tuple(
        it.chain(
            it.product(("manager",), range(managers)),
            it.product(("worker",), range(workers)),
        )
    )

    with futures.ThreadPoolExecutor() as ex:

        for role, number in machines_desired:

            ex.submit(
                c.run,
                f"""
                docker-machine create \
                    --driver google \
                    --google-project {project} \
                    --google-zone {zone} \
                    --google-machine-type {machine_type} \
                    --google-tags docker \
                    swarm-{role}-{number}
                """,
                warn=True,
            )

    for role, number in machines_desired:

        machine_name = f"swarm-{role}-{number}"

        if role == "manager" and number == 0:

            manager_name = machine_name

            manager_ip = c.run(
                f"""
                gcloud compute instances describe \
                    --project {project} \
                    --zone {zone} \
                    --format 'value(networkInterfaces[0].networkIP)' \
                    {machine_name}
                """
            ).stdout.strip()

            c.run(
                f"""
                docker-machine ssh {machine_name} sudo docker swarm init \
                    --advertise-addr {manager_ip}
                """,
                warn=True,
            )
        elif role == "manager":
            manager_token = c.run(
                f"docker-machine ssh {manager_name} sudo docker swarm join-token manager | grep token |"
                + " awk '{ print $5 }'"
            ).stdout.strip()

            c.run(
                f"""
                docker-machine ssh {machine_name} sudo docker swarm join \
                    --token {manager_token} \
                    {manager_ip}:2377
                """,
                warn=True,
            )
        else:
            worker_token = c.run(
                f"docker-machine ssh {manager_name}"
                + " sudo docker swarm join-token worker | grep token | awk '{ print $5 }'"
            ).stdout.strip()

            c.run(
                f"""
                docker-machine ssh {machine_name} sudo docker swarm join \
                    --token {worker_token} \
                    {manager_ip}:2377
                """,
                warn=True,
            )


@task
def swarm_down(c):
    """Take the swarm workers down."""
    configure_prod_or_local(c, prod=False)
    with futures.ThreadPoolExecutor() as ex:
        for line in c.run("docker-machine ls", hide=True).stdout.splitlines()[
            1:
        ]:
            if not any(
                line.startswith(n) for n in ("swarm-manager", "swarm-worker")
            ):
                continue
            name, *_ = line.split()
            ex.submit(c.run, f"docker-machine rm -f {name}", warn=True)


@task
def rebuild(c):
    """Rebuild and push to remote repository."""
    c.run("docker-compose build")
    c.run("docker-compose push", pty=True)


@task(aliases=["up"])
def deploy(c, rebuild_=False, stack=False, prod=False, ngrok=False):
    """
    Deploy the airflow instance.

    Args:
        c: invoke context
        rebuild_: rebuild the images prior to deployment
        stack: use docker swarm mode
        prod: deploy to production
        ngrok: deploy locally, but expose to internet via ngrok

    """
    configure_prod_or_local(c, prod)
    if ngrok:
        if rebuild_:
            rebuild(c)
        atexit.register(c.run, "docker-compose down")
        c.run("docker-compose up -d")
        c.run("ngrok http 8080", pty=True)
    elif prod or stack:
        if prod or rebuild_:
            rebuild(c)
        c.run(
            f"docker stack deploy -c docker-compose.yaml -c docker-compose.prod.yaml {c.config.stack_name}"
        )
    else:
        if rebuild_:
            rebuild(c)
        c.run(f"docker-compose up")


@task(aliases=["down"])
def undeploy(c, prod=False):
    """Tear down the code that's deployed."""
    configure_prod_or_local(c, prod)
    c.run(f"docker stack remove {c.config.stack_name}")


@task
def status(c, prod=False):
    """View the status of the deployed services."""
    configure_prod_or_local(c, prod)
    c.run(f"docker service ls")


@task(aliases=["add-ingress"])
def expose_thyself(
    c, name=None, rules="tcp:80,tcp:443", service="reverse-proxy"
):
    """Expose our app to the outside world."""

    name = c.config.stack_name + "-ingress" if name is None else name

    c.run(
        f"""
        gcloud compute firewall-rules create '{name}' \
        --project={c.config.gcp.project} \
        --description='Allow ingress into our docker swarm for {service}' \
        --direction=INGRESS \
        --priority=1000 \
        --network=default \
        --action=ALLOW \
        --rules={rules} \
        --target-tags=docker-machine
        """
    )


@task(aliases=["rm-ingress"])
def unexpose_thyself(c, name=None):
    """Unexpose our app to the outside world."""

    name = c.config.stack_name + "-ingress" if name is not None else name

    c.run(f"gcloud compute firewall-rules delete {name}")


@task
def get_swarm_machine_env(c, machine="swarm-manager-0"):
    """Return a swarm machine's docker env vars as a dict."""
    result = {}
    output = shell(["docker-machine", "env", machine]).stdout
    for line in output.splitlines():
        if "=" in line:
            key, value = line.split("=")
            *_, key = key.split()
            value = value.strip('"')
            result[key] = value
    pprint(result)
    return result


def configure_prod_or_local(c, prod=False):
    """Configure the execution environment based on whether we're deploying locally or to prod."""
    env_vars = (
        "DOCKER_TLS_VERIFY",
        "DOCKER_HOST",
        "DOCKER_CERT_PATH",
        "DOCKER_MACHINE_NAME",
    )

    if prod:
        c.config.run.update({"env": get_swarm_machine_env(c)})
    else:
        for var in (v for v in env_vars if v in os.environ):
            os.environ.pop(var)


@task
def encrypt(
    c, source, key=None, destination=None, location=None, keyring=None
):
    """
    Encrypt a file using google cloud kms.

    Args:
        source: The source file to be encrypted
        key: The name of the key
        destination: The file that will be created by encryption
        location: gcp zone
        keyring: gcp kms keyring
    """
    destination = destination if destination is not None else source + ".enc"
    location = location if location is not None else c.config.gcp.kms.location
    keyring = keyring if keyring is not None else c.config.gcp.kms.keyring
    key = key if key is not None else c.config.gcp.kms.key

    c.run(
        f"gcloud kms encrypt --key={key} --location={location} --keyring={keyring} "
        f"--plaintext-file={source} --ciphertext-file={destination}"
    )


@task
def encrypt_files(c):
    """
    Encrypt files in invoke.yaml encrypt.files
    """

    for f in c.config.encrypt.files:
        encrypt(c, Path(f).__fspath__())


@task(aliases=["gen-cert"])
def create_certificate(c, days=365):
    """
    Generate a TLS certificate and key pair.

    Args:
        c: invoke context
        days: the number of days till your certificate expires

    """
    c.run(
        f"openssl req -x509 -nodes -days 365 -newkey rsa:2048 -keyout "
        f"reverse-proxy/key.key -out reverse-proxy/certificate.crt"
    )


@task
def new_dag(
    c,
    dag_id=None,
    owner=None,
    email=None,
    start_date=None,
    schedule_interval=None,
    force=False,
):
    """
    Render a new dag and put it in the dags folder.

    Args:
        c: invoke context
        dag_id: i.e. my_dag_v1_p3 (dag_name, version, priority[1-high, 2-med, 3-low])
        owner: you
        email: your email
        start_date: date in iso format
        schedule_interval: cron expression
        force: overwrite dag module if it exists

    """

    yesterday = dt.date.today() - dt.timedelta(days=1)
    # v - version
    # p - priority (1, 2, 3) == (high, medium, low)
    defaults = {
        "dag_id": "example_dag_v1_p3",
        "owner": "Stephan Fitzpatrick",
        "email": "knowsuchagency@gmail.com",
        "start_date": yesterday.isoformat(),
        "schedule_interval": "0 7 * * *",
    }

    template_text = read_text("flow_toolz.templates", "dag_template.py")

    template = Template(template_text)

    args = {}

    locals_ = locals()

    print(
        "rendering your new dag. please enter the following values:",
        end=os.linesep * 2,
    )

    for key, default_value in defaults.items():

        explicit_value = locals_[key]

        if explicit_value:
            args[key] = explicit_value
        else:
            value = input(f"{key} (default: {default_value}) -> ").strip()

            args[key] = value or defaults[key]

    rendered_text = template.render(**args)

    print()

    filename = re.sub(r"_v[^.]+", "", args["dag_id"], re.IGNORECASE) + ".py"

    dag_path = Path("airflow", "dags", filename)

    if dag_path.exists() and not force:
        raise SystemExit(f"{filename} already exists. aborting")

    print(f"writing dag to: {dag_path}")

    dag_path.write_text(rendered_text + os.linesep)


@task
def connect(c):
    """Connect to airflow deployment."""
    manager_ip = c.run("docker-machine ip swarm-manager-0").stdout
    c.run(f"open http://{manager_ip}")


@task(aliases=["bootstrap"])
def generate_auth_files(c):
    """Generate ssl keys and other file stubs for authentication purposes."""
    create_certificate(c)

    for filename in c.config.encrypt.files:
        filepath = Path(filename)
        if not filepath.exists():
            filepath.touch()
