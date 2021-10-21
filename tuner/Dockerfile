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
RUN git clone git://git.osmocom.org/rtl-sdr.git /tmp/rtl-sdr
WORKDIR /tmp/rtl-sdr
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
RUN git clone https://github.com/jorisvr/SoftFM.git /tmp/SoftFM
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

# bootstrap dependencies
RUN dnf -y install make
RUN dnf -y install python-virtualenv python2

# dependencies of airspy and ffmpeg
RUN dnf -y install portaudio
RUN dnf -y install volk
RUN dnf -y install soxr
RUN dnf -y install https://mirrors.rpmfusion.org/free/fedora/rpmfusion-free-release-34.noarch.rpm https://mirrors.rpmfusion.org/nonfree/fedora/rpmfusion-nonfree-release-34.noarch.rpm
RUN dnf -y install ffmpeg
RUN dnf -y install strace
RUN dnf -y install /usr/sbin/atd
RUN dnf -y install /usr/bin/find
RUN dnf -y install libfaketime

# Set default workdir
RUN mkdir -p /tmp/pysched
WORKDIR /tmp/pysched

# initialize virtualenv
COPY Makefile.tuner Makefile
COPY requirements.txt ./
RUN make pysched

# Install softfm / airspy / RTL-SDR from first stage build
COPY --from=softfm /tmp/SoftFM/build/softfm pysched/bin/softfm
COPY --from=softfm /tmp/airspy-fmradion/build/airspy-fmradion pysched/bin/airspy-fmradion
COPY --from=softfm /usr/local/lib/pkgconfig/librtlsdr.pc /usr/local/lib/pkgconfig/
COPY --from=softfm /usr/local/include/rtl-sdr*.h /usr/local/include/
COPY --from=softfm /usr/local/lib/librtlsdr.* /usr/local/lib/
COPY --from=softfm /usr/local/bin/rtl_* /usr/local/bin/

# tune.py and dependencies
COPY units.txt config.json tune.py favicon.ico ./
COPY templates templates

# make empty dirs
RUN mkdir -p js
RUN mkdir -p css
RUN mkdir -p data

ENTRYPOINT ["/tmp/pysched/tune.py"]
