<img width="452" alt="image" src="https://github.com/user-attachments/assets/530a3178-4d11-49bc-8767-e30698f783f2" />


# 개발 환경 및 실행 방법

## 시스템 환경 및 의존성 설치
시스템 업데이트
•	sudo apt update && sudo apt upgrade -y

Python 3 및 pip 설치
•	sudo apt install -y python3 python3-pip

Docker 및 Docker Compose 설치
•	sudo apt install -y docker.io docker-compose

htpasswd 생성을 위한 패키지
•	sudo apt install -y apache2-utils

현재 사용자를 docker 그룹에 추가
•	sudo usermod -aG docker $USER

위 명령 실행 후, 적용을 위해, 종료 후 재접속

## 프로젝트 실행
•	cd private-registry/
•	docker-compose up --build -d


## 기능들을 사용하기 위해서, 최초로 관리자 초기화를 진행해야함


# 디렉토리 구조
private-registry/
├── auth/
├── backend/
│   ├── app.py
│   ├── audit.log
│   ├── registry_api.py
│   ├── requirements.txt
│   └── Dockerfile
├── registry/
│   └── data/
├── docker-compose.yml
