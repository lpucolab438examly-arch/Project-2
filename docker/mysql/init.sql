# MySQL initialization script
CREATE DATABASE IF NOT EXISTS fraudnet_ai;
CREATE DATABASE IF NOT EXISTS test_fraudnet_ai;

# Create user if not exists
CREATE USER IF NOT EXISTS 'fraudnet_user'@'%' IDENTIFIED BY 'fraudnet_password';
CREATE USER IF NOT EXISTS 'test_user'@'%' IDENTIFIED BY 'test_password';

# Grant privileges
GRANT ALL PRIVILEGES ON fraudnet_ai.* TO 'fraudnet_user'@'%';
GRANT ALL PRIVILEGES ON test_fraudnet_ai.* TO 'test_user'@'%';

FLUSH PRIVILEGES;