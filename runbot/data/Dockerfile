FROM debian:stretch
ENV LANG C.UTF-8
USER root
# Install base files
RUN set -x ; \
    apt-get update \
    && apt-get install -y --no-install-recommends \
    apt-transport-https \
    build-essential \
    ca-certificates \
    curl \
    gawk \
    gnupg \
    libldap2-dev \
    libsasl2-dev \
    libxslt1-dev \
    node-less \
    python \
    python-dev \
    python-pip \
    python3 \
    python3-dev \
    python3-pip \
    python3-setuptools \
    python3-wheel \
    sed \
    sudo \
    xfonts-75dpi \
    zlib1g-dev

# Install Google Chrome
RUN curl -sSL https://dl.google.com/linux/linux_signing_key.pub | apt-key add - \
    && echo "deb https://dl.google.com/linux/chrome/deb/ stable main" > /etc/apt/sources.list.d/google-chrome.list \
    && apt-get update \ 
    && apt-get install -y -qq google-chrome-stable

# Install phantomjs
RUN curl -sSL https://bitbucket.org/ariya/phantomjs/downloads/phantomjs-2.1.1-linux-x86_64.tar.bz2  -o /tmp/phantomjs.tar.bz2 \
    && tar xvfO /tmp/phantomjs.tar.bz2 phantomjs-2.1.1-linux-x86_64/bin/phantomjs > /usr/local/bin/phantomjs \
    && chmod +x /usr/local/bin/phantomjs \
    && rm -f /tmp/phantomjs.tar.bz2

# Install wkhtml and setup odoo user
RUN curl -sSL https://github.com/wkhtmltopdf/wkhtmltopdf/releases/download/0.12.5/wkhtmltox_0.12.5-1.stretch_amd64.deb -o /tmp/wkhtml.deb \
    && dpkg --force-depends -i /tmp/wkhtml.deb \
    && apt-get install -y -f --no-install-recommends \
    && rm /tmp/wkhtml.deb \
    && groupadd -g 1000 odoo \
    && useradd -u 1000 -g odoo -G audio,video odoo \
    && mkdir /home/odoo \
    && chown -R odoo:odoo /home/odoo \
    && echo "odoo ALL= NOPASSWD: /usr/bin/pip" > /etc/sudoers.d/pip \
    && echo "odoo ALL= NOPASSWD: /usr/bin/pip3" >> /etc/sudoers.d/pip

# Install Odoo Debian dependencies
ADD https://raw.githubusercontent.com/odoo/odoo/10.0/debian/control /tmp/p2-control
ADD https://raw.githubusercontent.com/odoo/odoo/master/debian/control /tmp/p3-control
RUN sed -n '/^Depends:/,/^[A-Z]/p' /tmp/p2-control /tmp/p3-control | awk '/^ [a-z]/ { gsub(/,/,"") ; print }' | sort -u | sed 's/python-pypdf/python-pypdf2/' | xargs apt-get install -y -qq \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Install Odoo requirements for python2 and python3 not fullfilled by Debian dependencies
ADD https://raw.githubusercontent.com/odoo/odoo/master/requirements.txt /root/p3-requirements.txt
ADD https://raw.githubusercontent.com/odoo/odoo/10.0/requirements.txt /root/p2-requirements.txt
RUN ["/bin/bash", "-c", "pip3 install --no-cache-dir -r /root/p3-requirements.txt && pip3 install websocket-client && pip install --no-cache-dir -r /root/p2-requirements.txt"]

# Runbot build will be launched as user odoo
USER odoo
ENV COVERAGE_FILE /data/build/.coverage
