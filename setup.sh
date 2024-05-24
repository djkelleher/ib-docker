#!/bin/bash

apt-get -y update
apt-get -y dist-upgrade
DEBIAN_FRONTEND=noninteractive apt-get -y install --no-install-recommends \
    wget ca-certificates unzip software-properties-common locales nano gettext-base xvfb x11vnc
# X11 forwarding for running on local machine.
#libx11-6 libxext-dev libxtst-dev libxrender1 libfontconfig1 \
# X server, VNC server, window manager for server deployments.

if [ ${PROGRAM} = "ibgateway" ]; then
    IB_RELEASE_DIR=/opt/ibgateway/${IB_RELEASE}
    mkdir -p $IB_RELEASE_DIR
    mv /jts.ini $IB_RELEASE_DIR/jts.ini
else
    IB_RELEASE_DIR=/Jts/$IB_RELEASE
    mkdir /Jts
    mv /jts.ini /Jts/jts.ini
    DEBIAN_FRONTEND=noninteractive apt-get -y install --no-install-recommends libavcodec-dev \
        libavformat-dev libgtk-3-dev libasound2 libnss3 libnspr4
fi
apt-get autoremove -y --purge
apt-get clean -y
rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*
sed -i -e 's/# en_US.UTF-8 UTF-8/en_US.UTF-8 UTF-8/' /etc/locale.gen
locale-gen
update-locale LANG=en_US.UTF-8 LC_ALL=en_US.UTF-8
# Install Gateway or TWS.
echo "Installing ${PROGRAM}"
if [ ${VERSION} = "NULL" ]; then
    PROG_FILE_URL=https://download2.interactivebrokers.com/installers/${PROGRAM}/${IB_RELEASE}-standalone/${PROGRAM}-${IB_RELEASE}-standalone-linux-${ARCH}.sh
    echo "Downloading ${PROG_FILE_URL}"
    wget -q -O /ib.sh $PROG_FILE_URL
else
    PROG_FILE_NAME=ibgateway-${IB_RELEASE}-${VERSION}-standalone-linux-x64.sh
    PROG_FILE_URL=https://github.com/djkelleher/ib-docker/releases/download/${IB_RELEASE}-${VERSION}/$PROG_FILE_NAME
    wget -q -O /$PROG_FILE_NAME $PROG_FILE_URL
    wget -q -O /$PROG_FILE_NAME.sha256 $PROG_FILE_URL.sha256
    sha256sum --check /$PROG_FILE_NAME.sha256
    mv /$PROG_FILE_NAME /ib.sh
fi
chmod +x /ib.sh
if [ "$(uname -m)" = "aarch64" ]; then
    echo "Installing custom Java release for aarch64."
    wget -q -O bellsoft.tar.gz "https://download.bell-sw.com/java/11.0.22+12/bellsoft-jre11.0.22+12-linux-aarch64-full.tar.gz"
    tar -xvzf bellsoft.tar.gz
    export JVM_DIR="jre-11.0.22-full"
    export JAVA_HOME=/opt/java
    mv jre-11.0.22-full $JAVA_HOME
    export PATH=$JAVA_HOME/bin:$PATH
    sed -i 's/-Djava.ext.dirs="$app_java_home\/lib\/ext:$app_java_home\/jre\/lib\/ext"/--add-modules=ALL-MODULE-PATH/g' "/ib.sh"
    app_java_home=/opt/java /ib.sh -q -dir ${IB_RELEASE_DIR}
else
    /ib.sh -q -dir ${IB_RELEASE_DIR}
#rm /ib.sh; \
fi
# Install IBC
echo "Installing IBC"
wget -q -O /tmp/IBC.zip ${IBC_RELEASE}
unzip /tmp/IBC.zip -d ${IBC_PATH}
chmod -R u+x ${IBC_PATH}/*.sh
chmod -R u+x ${IBC_PATH}/scripts/*.sh
rm -f /tmp/IBC.zip
