# Ubuntu lab SSH authentication server for the project-owned test environment.
# Multi-arch official Ubuntu image (works on Apple Silicon and amd64).
FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive \
    LAB_SSH_USER=testuser \
    LAB_SSH_PASSWORD=change_me_for_local_lab

# Minimal packages: OpenSSH for auth events, rsyslog for auth.log,
# procps for process-based healthcheck (avoids SSH handshake noise in auth.log).
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        openssh-server \
        rsyslog \
        passwd \
        bash \
        ca-certificates \
        procps \
    && rm -rf /var/lib/apt/lists/* \
    && mkdir -p /var/run/sshd /var/log/auth-lab \
    && ssh-keygen -A \
    && if [ -f /etc/rsyslog.conf ]; then \
         sed -i -E 's/^(\s*module\(load="imklog".*)/# \1/' /etc/rsyslog.conf; \
         sed -i -E 's/^(\$ModLoad[[:space:]]+imklog)/# \1/' /etc/rsyslog.conf; \
       fi

# Lab-specific SSH + syslog configuration
COPY sshd_config /etc/ssh/sshd_config
COPY rsyslog-auth.conf /etc/rsyslog.d/30-auth-lab.conf
COPY entrypoint.sh /usr/local/bin/lab-entrypoint.sh

RUN chmod 755 /usr/local/bin/lab-entrypoint.sh \
    && chmod 600 /etc/ssh/sshd_config \
    && touch /var/log/auth-lab/auth.log

EXPOSE 22

# Process check confirms sshd is running without opening a fake SSH client session.
HEALTHCHECK --interval=5s --timeout=3s --retries=10 --start-period=15s \
    CMD pgrep -x sshd >/dev/null || exit 1

ENTRYPOINT ["/usr/local/bin/lab-entrypoint.sh"]
