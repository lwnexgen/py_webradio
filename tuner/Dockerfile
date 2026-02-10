FROM fedora:34 AS softfm

RUN dnf -y install alsa-lib alsa-lib-devel cmake gcc gcc-c++ git libsndfile libsndfile-devel libsndfile-utils libusb libusb-devel make numpy pkgconf portaudio portaudio-devel python2 python3 python3-virtualenv soxr soxr-devel volk volk-devel

# Build RTL-SDR from source
# RUN git clone --single-branch --branch v0.5.4 git://git.osmocom.org/rtl-sdr.git /tmp/rtl-sdr
RUN git clone --single-branch --branch v0.5.4 https://github.com/osmocom/rtl-sdr /tmp/rtl-sdr
WORKDIR /tmp/rtl-sdr
RUN mkdir build
WORKDIR build
RUN cmake ../ && make install && ldconfig

# Build airspyhf
RUN git clone --single-branch --branch master https://github.com/airspy/airspyhf.git /tmp/airspyhf
RUN mkdir /tmp/airspyhf/build
WORKDIR /tmp/airspyhf/build
RUN cmake .. && make install && ldconfig

# # Build airspy
RUN git clone https://github.com/airspy/airspyone_host.git /tmp/airspyone_host
RUN mkdir /tmp/airspyone_host/build
WORKDIR /tmp/airspyone_host/build
RUN cmake .. && make install && ldconfig

# Build airspy-fmradion
RUN git clone -b 20211101-0 https://github.com/jj1bdx/airspy-fmradion.git /tmp/airspy-fmradion
RUN mkdir /tmp/airspy-fmradion/build
WORKDIR /tmp/airspy-fmradion/build
RUN cmake .. && make -j4

FROM fedora:34

# bootstrap dependencies
RUN dnf -y install https://mirrors.rpmfusion.org/nonfree/fedora/rpmfusion-nonfree-release-34.noarch.rpm https://mirrors.rpmfusion.org/free/fedora/rpmfusion-free-release-34.noarch.rpm && dnf -y install make python-virtualenv python2 portaudio volk soxr ffmpeg strace /usr/bin/find libfaketime zstd

# download Python from upstream astral-sh
RUN curl -L "https://github.com/astral-sh/python-build-standalone/releases/download/20260203/cpython-3.12.12+20260203-x86_64_v2-unknown-linux-gnu-pgo+lto-full.tar.zst" -o /tmp/python.tar.zst
RUN tar -xf /tmp/python.tar.zst -C /tmp/

ENV PATH="/tmp/python/install/bin:${PATH}"

# Set default workdir
RUN mkdir -p /tmp/pysched
WORKDIR /tmp/pysched

# initialize virtualenv
COPY Makefile.tuner Makefile
COPY requirements.txt ./
RUN make pysched

# Install softfm / airspy / RTL-SDR from first stage build
COPY --from=softfm /tmp/airspy-fmradion/build/airspy-fmradion pysched/bin/airspy-fmradion
COPY --from=softfm /usr/local/lib/pkgconfig/librtlsdr.pc /usr/local/lib/pkgconfig/
COPY --from=softfm /usr/local/include/rtl-sdr*.h /usr/local/include/
COPY --from=softfm /usr/local/lib/librtlsdr.* /usr/local/lib/
COPY --from=softfm /usr/local/bin/rtl_* /usr/local/bin/

# tune.py and dependencies
COPY units.txt config.json favicon.ico ./
COPY templates templates

# make empty dirs
RUN mkdir -p js
RUN mkdir -p css
RUN mkdir -p data

COPY tuner.json ./
COPY fscfg.json ./
COPY tune.py ./

ENTRYPOINT ["/tmp/pysched/tune.py"]
