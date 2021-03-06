FROM ubuntu:16.04
MAINTAINER ultmaster scottyugochang@hotmail.com
ENV DEBIAN_FRONTEND noninteractive

RUN apt-get update \
    && apt-get -y install software-properties-common python-software-properties python python-dev python-pip \
                          locales python3-software-properties python3 python3-dev python3-pip \
                          gcc g++ git libtool python-pip libseccomp-dev cmake openjdk-8-jdk nginx redis-server \
                          mono-devel php gfortran perl ghc scala nodejs nodejs-legacy \
                          rustc fp-compiler clang pypy mono-complete ocaml-nox memcached libboost-all-dev \
                          wget \
    && add-apt-repository ppa:ubuntu-toolchain-r/test \
    && apt-get update \
    && apt-get -y install g++-7 \
    && wget https://bitbucket.org/pypy/pypy/downloads/pypy3-v6.0.0-linux64.tar.bz2 \
    && tar -xvf pypy3-v6.0.0-linux64.tar.bz2 \
    && ln -s /pypy3-v6.0.0-linux64/bin/pypy3 /usr/local/bin/pypy3 \
    && rm pypy3-v6.0.0-linux64.tar.bz2 \
    && locale-gen en_US.UTF-8 \
    && mkdir -p /ejudge
COPY . /ejudge
WORKDIR /ejudge
ENV LANG=en_US.UTF-8 LANGUAGE=en_US:en LC_ALL=en_US.UTF-8
RUN useradd -r compiler \
    && wget https://raw.githubusercontent.com/MikeMirzayanov/testlib/master/testlib.h -O /usr/local/include/testlib.h \
    && cp sandbox/java_policy /etc/ \
    && pip3 install -r requirements.txt \
    && python3 setup.py build_ext --inplace \
    && chmod 600 config/* \
    && chmod +x run.sh
EXPOSE 5000

CMD ./run.sh
