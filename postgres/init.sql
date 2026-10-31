-- отдельная база и учётная запись для каждого сервиса, работающего с БД (изоляция данных)
CREATE USER booking WITH PASSWORD 'booking';
CREATE DATABASE booking_db OWNER booking;
CREATE USER payment WITH PASSWORD 'payment';
CREATE DATABASE payment_db OWNER payment;
CREATE USER users WITH PASSWORD 'users';
CREATE DATABASE users_db OWNER users;
CREATE USER catalog WITH PASSWORD 'catalog';
CREATE DATABASE catalog_db OWNER catalog;
CREATE USER notification WITH PASSWORD 'notification';
CREATE DATABASE notification_db OWNER notification;
