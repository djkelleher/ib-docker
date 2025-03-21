FROM ubuntu:22.04

ENV LC_ALL C.UTF-8
ENV LANG en_US.UTF-8
ENV LANGUAGE en_US.UTF-8

ARG VERSION=NULL
# program can be tws or ibgateway.
ARG PROGRAM=ibgateway
# release can be stable, latest, or beta; 
ARG RELEASE=stable
# arch can be x64 or x86.
ARG ARCH=x64

ARG IBC_RELEASE=https://github.com/IbcAlpha/IBC/releases/download/3.21.2/IBCLinux-3.21.2.zip

ENV PROGRAM=${PROGRAM}
ENV IB_RELEASE=${RELEASE}

ENV IBC_PATH=/opt/ibc
ENV IBC_INI=${IBC_PATH}/ibc.ini

ENV SCRIPT_PATH=/scripts

# this will get moved depending on PROGRAM argument
COPY jts.ini /jts.ini
COPY setup.sh /setup.sh

RUN chmod +x /setup.sh && /setup.sh
# Add a few variables to ensure memory management in a container works
# Force anti-aliasing to LCD as JRE relies on xsettings, which are
# not present inside the container.
#echo " \n\
# Force LCD anti-aliasing \n\
#-Dawt.useSystemAAFontSettings=lcd \n\
# Respect container memory limits \n\
#-XX:+UnlockExperimentalVMOptions \n\
#-XX:+UseCGroupMemoryLimitForHeap \n\
#" >> ${IB_RELEASE_DIR}/${PROGRAM}.vmoptions

# Bundle the Google Noto Sans Mono Medium font
# https://www.google.com/get/noto/
# SIL Open Font License, Version 1.1

# create a file to signal that the env vars need to be set.
RUN touch /process_env_vars

# Bundle the Google Noto Sans Mono Medium font
# https://www.google.com/get/noto/
# SIL Open Font License, Version 1.1
#COPY fonts/* /.fonts/
#RUN fc-cache

COPY ibc.ini ${IBC_INI}
COPY ibc_${PROGRAM}.sh /usr/local/bin/ibc_${PROGRAM}
COPY ${PROGRAM}.sh /usr/local/bin/${PROGRAM}
COPY common.sh $SCRIPT_PATH/common.sh
RUN /bin/bash -c "chmod +x /usr/local/bin/{ibc_${PROGRAM},${PROGRAM}}"

CMD "ibc_${PROGRAM}"