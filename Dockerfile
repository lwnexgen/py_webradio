FROM fedora:latest AS softfm

RUN dnf -y install python3 python3-virtualenv cmake numpy gcc
RUN dnf -y install gcc-c++ gcc
RUN dnf -y install alsa-lib alsa-lib-devel
RUN dnf -y install libusb libusb-devel
RUN dnf -y install git
RUN dnf -y install make
RUN dnf -y install pkgconf
RUN dnf -y install python2
RUN dnf -y install soxr soxr-devel
RUN dnf -y install portaudio portaudio-devel

# Build RTL-SDR from source
RUN git clone git://git.osmocom.org/rtl-sdr.git
WORKDIR rtl-sdr
RUN git checkout v0.5.4
RUN mkdir build
WORKDIR build
RUN cmake ../
RUN make uninstall ||:
RUN make
RUN make install
RUN ldconfig

# Build airspyhf
RUN git clone https://github.com/airspy/airspyhf.git /tmp/airspyhf
RUN mkdir /tmp/airspyhf/build
WORKDIR /tmp/airspyhf/build
RUN cmake ..
RUN make
RUN make install
RUN ldconfig

# Build SoftFM
RUN mkdir -p /tmp
WORKDIR /tmp
COPY SoftFM /tmp/SoftFM
RUN rm -rf /tmp/SoftFM/build
RUN mkdir /tmp/SoftFM/build
WORKDIR /tmp/SoftFM/build
RUN ls -ltr ../
RUN cmake -DRTLSDR_INCLUDE_DIR=/usr/local/include ..
RUN make

# Build airspy
RUN git clone https://github.com/airspy/airspyone_host.git /tmp/airspyone_host
RUN mkdir /tmp/airspyone_host/build
WORKDIR /tmp/airspyone_host/build
RUN cmake ..
RUN make
RUN make install
RUN ldconfig

# Build airspy-fmradion
RUN dnf -y install volk volk-devel libsndfile libsndfile-utils libsndfile-devel
RUN git clone https://github.com/jj1bdx/airspy-fmradion.git /tmp/airspy-fmradion
RUN mkdir /tmp/airspy-fmradion/build
WORKDIR /tmp/airspy-fmradion/build
RUN cmake ..
RUN make -j4

FROM fedora:latest

RUN dnf -y install python3 python3-virtualenv cmake numpy gcc
RUN dnf -y install gcc-c++ gcc
RUN dnf -y install alsa-lib alsa-lib-devel
RUN dnf -y install libusb libusb-devel
RUN dnf -y install make git
RUN dnf -y install at
RUN dnf -y install python2
RUN dnf -y install https://mirrors.rpmfusion.org/free/fedora/rpmfusion-free-release-34.noarch.rpm https://mirrors.rpmfusion.org/nonfree/fedora/rpmfusion-nonfree-release-34.noarch.rpm
RUN dnf -y install ffmpeg
RUN dnf -y install strace
RUN dnf -y install airspyone_host airspyone_host-devel
RUN dnf -y install soxr soxr-devel
RUN dnf -y install portaudio portaudio-devel
RUN dnf -y install portaudio portaudio-devel
RUN dnf -y install volk volk-devel

# Build libfaketime from source
RUN git clone https://github.com/wolfcw/libfaketime.git
WORKDIR libfaketime
RUN git checkout 3c0b101a84de6eb9b05f8181c3f40731575e9ebc
RUN make
RUN make install
WORKDIR ..

# Build RTL-SDR from source
RUN git clone git://git.osmocom.org/rtl-sdr.git
WORKDIR rtl-sdr
RUN git checkout v0.5.4
RUN mkdir build
WORKDIR build
RUN cmake ../
RUN make uninstall ||:
RUN make
RUN make install
RUN ldconfig

RUN mkdir -p /tmp/pysched
WORKDIR /tmp/pysched

COPY config.json root-setup.sh *.py *.html *.ico units.txt requirements.txt ./

RUN virtualenv -p python2 pysched
RUN sh root-setup.sh
COPY --from=softfm /tmp/SoftFM/build/softfm pysched/bin/softfm
COPY --from=softfm /tmp/airspy-fmradion/build/airspy-fmradion pysched/bin/airspy-fmradion
COPY js js
COPY css css
COPY sports sports
COPY data data
COPY templates templates
COPY Makefile Makefile

# RUN useradd sam
# RUN chown -R sam:sam /tmp/pysched
# USER sam

COPY entrypoint-tuner.sh /tmp/entrypoint-docker.sh

COPY entrypoint.py /tmp/pysched/entrypoint.py
ENTRYPOINT /tmp/pysched/entrypoint.py
CMD ""
