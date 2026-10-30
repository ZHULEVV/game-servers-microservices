-- отдельная база и учётная запись для каждого сервиса (изоляция данных)
CREATE USER booking WITH PASSWORD 'booking';
CREATE DATABASE booking_db OWNER booking;
CREATE USER payment WITH PASSWORD 'payment';
CREATE DATABASE payment_db OWNER payment;
