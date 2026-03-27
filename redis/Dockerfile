FROM redis:7.4-alpine

COPY redis.conf /usr/local/etc/redis/redis.conf
COPY conf.d /usr/local/etc/redis/conf.d

VOLUME ["/data"]
EXPOSE 6379

CMD ["redis-server", "/usr/local/etc/redis/redis.conf"]
