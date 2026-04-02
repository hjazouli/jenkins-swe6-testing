pipeline {
    agent any
    
    triggers {
        // Trigger the build exactly after a push to GitHub via webhook
        githubPush()
        // Alternatively, use polling (e.g., every minute) if webhooks can't reach your local network:
        // pollSCM('* * * * *')
    }
    
    environment {
        PYTHON_ENV = 'python3'
        ECU_TARGET = 'TC397'
        FIRMWARE_BINARY = 'build/firmware.elf'
    }
    
    stages {
        stage('Checkout') {
            steps {
                echo '📦 Pulling latest code...'
                // checkout scm
            }
        }
        
        stage('Build Firmware') {
            steps {
                echo '🔨 Compiling ECU firmware...'
                sh 'make clean'
                sh 'make'
            }
        }
        
        stage('Flash ECU (Lauterbach Mock)') {
            steps {
                echo '⚡ Flashing firmware to mock ECU...'
                sh "python3 scripts/mock_lauterbach.py ELF_PATH=${FIRMWARE_BINARY}"
            }
        }
        
        stage('Run Pytest Suite (Virtual CAN)') {
            steps {
                echo '🧪 Executing automated tests...'
                // Use virtual CAN for testing inside Jenkins
                sh "pip3 install -r requirements.txt"
                sh '''
                    python3 -m pytest \
                        tests/ \
                        --junitxml=test-results.xml \
                        --html=report.html \
                        --self-contained-html
                '''
            }
        }
        
        stage('Upload to Polarion (Mock Server)') {
            steps {
                echo '📊 Pushing results to Polarion...'
                sh '''
                    # Start mock server in background
                    python3 scripts/mock_polarion_server.py &
                    MOCK_SERVER_PID=$!
                    sleep 2
                    
                    # Upload results
                    python3 scripts/polarion_upload.py \
                        --xml test-results.xml \
                        --testrun "Build_${BUILD_NUMBER}"
                    
                    # Kill mock server
                    kill $MOCK_SERVER_PID
                '''
            }
        }
    }
    
    post {
        always {
            junit 'test-results.xml'
            archiveArtifacts artifacts: 'build/firmware.elf, report.html'
        }
        success {
            echo '✅ Pipeline passed! Virtual ECU verified.'
        }
        failure {
            echo '❌ Pipeline failed.'
        }
    }
}
