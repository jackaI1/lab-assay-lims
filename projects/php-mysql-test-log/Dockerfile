FROM php:8.4-cli-alpine3.23
RUN docker-php-ext-install pdo_mysql && apk add --no-cache unzip
COPY --from=composer:2 /usr/bin/composer /usr/local/bin/composer
WORKDIR /app
COPY composer.json composer.lock ./
RUN composer install --no-interaction --prefer-dist --no-progress
COPY . .
EXPOSE 8080
CMD ["sh", "-c", "php bin/migrate.php && php -S 0.0.0.0:8080 -t public public/router.php"]
