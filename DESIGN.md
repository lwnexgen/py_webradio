```
             ┌────────────────┐                                              ┌─────────────────┐
             │     tuner      │                                              │      sched      │
             │                │                                              │                 │
             │ listens for    │          ┌──────────────────────┐            │ script that     │
             │ cfg msgs from  │          │         rmq          │            │ scrapes betting │
             │ sched via rmq  │          │ localhost-only       │            │ sites for games │
             │                │◄─────────┤ RabbitMQ instance for│◄───────────┤ that I want to  │
             │ requires priv  │          │ coordinating messages│            │ listen to       │
             │ access to HW on│          │ between containers   │            │                 │
             │ host system    │          └──────────────────────┘            │ dumps scraped   │
             │                │                                              │ info in JSON to │
             │ background     │                                              │ RabbitMQ via    │
       ┌─────┤ processes that │                                              │ Pika            │
       │     │ sleep until    │                                              └─────────────────┘
       │     │ gametime       │
       │     └────────┬───────┘
       │              │
       │              │
       ▼              │
┌────────────────┐    │
│ triggers       │    │
│ RTL-SDR to     │    │
│ record FM      │    │ writes some basic html/css/js via templates
│ broadcast data │    │ to provide a frontend that I can access audio on
└────────────────┘    │
       ▼              │
┌────────────────┐    │
│pipes to ffmpeg │    │
│which turns raw │    │
│audio data into │    │
│hls/mp3 stream  │    │
│that Chrome can │    │
│play            │    │
└──────┬─────────┘    │
       │              │
       ▼              │
┌────────────────┐    │
│stores to shared│    │
│docker-compose  │    │
│volume          │◄───┘
│                │
│                ├───────────────────────┐
└────────────────┘                       │
                                         ▼
┌──────────────────────────────────────────────────────────────────────────────────────────────┐ ┌─────────────────────────────┐
│                                    nginx                                                     │ │       letsencrypt           │
│  very simple nginx instance that just serves up the recorded stream and the basic html       │ │ init container that         │
│  streaming frontend. uses geoip db to record country of origin on incoming requests so that  │ │ refreshes a cert for my     │
│  fail2ban can drop them.                                                                     │ │ domain as needed on cluster │
│                                                                                              │ │ startup                     │
└──────────────────────────────────────────────────────────────────────────────────────────────┘ └─────────────────────────────┘
```
