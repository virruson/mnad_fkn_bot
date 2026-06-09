**Подготовка ubunu сервера**

# Обнови пакеты
sudo apt update && sudo apt upgrade -y

# Установи зависимости
sudo apt install -y apt-transport-https ca-certificates curl software-properties-common

# Добавь официальный ключ Docker
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg

# Добавь репозиторий Docker
echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

# Установи Docker
sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io

# Добавь пользователя в группу docker (чтобы не использовать sudo)
sudo usermod -aG docker $USER

# Выйди и зайди заново (или выполни: newgrp docker)
exit
# Зайди снова
ssh username@server_ip_address

# Проверь Docker
docker --version

# Установи Docker Compose
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

# Проверь Docker Compose
docker-compose --version

# Создай директорию для проекта
mkdir -p ~/mnad_bot
cd ~/mnad_bot
git clone https://github.com/virruson/mnad_fkn_bot.git #надо права настроить

# 
~/mnad_bot/.env
chmod +x dockerfile dockerfile.migrations
chmod 600 .env


# Запусти в фоновом режиме
docker-compose up -d

# Посмотри логи
docker-compose logs -f

# Проверь статус контейнеров
docker-compose ps

# Просмотр логов
docker-compose logs -f bot
docker-compose logs -f postgres

# Перезапуск конкретного сервиса
docker-compose restart bot

# Остановка всех контейнеров
docker-compose down

# Перезапуск с пересборкой
docker-compose down
docker-compose up -d --build

# Просмотр использования ресурсов
docker stats