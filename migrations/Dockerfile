FROM ubuntu:jammy

RUN apt-get update && \
    apt-get install -y \
    curl 
    
RUN curl -L https://github.com/golang-migrate/migrate/releases/download/v4.16.2/migrate.linux-amd64.tar.gz | tar xvz && \
    ls -la && mv migrate /usr/local/bin/migrate

COPY . .
#make sure init.sh has correct line endings
RUN apt-get update && apt-get install -y dos2unix
RUN dos2unix ./init.sh && apt-get --purge remove -y dos2unix && rm -rf /var/lib/apt/lists/*
RUN chmod +x init.sh

RUN migrate -version
ENTRYPOINT ["./init.sh"]