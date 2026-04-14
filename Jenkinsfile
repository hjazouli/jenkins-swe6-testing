pipeline {
    agent any
    
    triggers {
        pollSCM('* * * * *')
    }
    
    environment {
        PYTHON_ENV = 'python3'
        ECU_TARGET = 'TC397'
        FIRMWARE_BINARY = 'build/firmware.elf'
    }
    
    stages {
        stage('Checkout') {
            steps {
                echo '📦 Pulling latest code and preparing venv...'
                // checkout scm
                sh '''
                    if [ ! -d ".venv" ]; then
                        python3 -m venv .venv
                    fi
                    .venv/bin/pip install --upgrade pip
                    .venv/bin/pip install -r requirements.txt
                '''
            }
        }
        
        stage('Set Build Name') {
            steps {
                script {
                    currentBuild.displayName = "#${BUILD_NUMBER} - ${env.BRANCH_NAME ?: 'main'} - ${env.GIT_COMMIT ? env.GIT_COMMIT[0..6] : 'unknown'}"
                    currentBuild.description = "Triggered by: ${env.CHANGE_AUTHOR ?: 'scheduler'}"
                }
            }
        }
        
        stage('Build Firmware') {
            steps {
                echo '🔨 Compiling ECU firmware...'
                sh 'make clean'
                sh 'make'
            }
        }
        
        stage('ASW Unit Tests (C)') {
            steps {
                echo '🧪 Executing ASW Unit Tests: Brake Logic...'
                sh 'make test_bcm'
            }
        }
        
        stage('BSW Unit Tests: Scheduler (C)') {
            steps {
                echo '🧪 Executing BSW Unit Tests: Scheduler...'
                sh 'make test_schm'
            }
        }

        stage('BSW Unit Tests: CAN (C)') {
            steps {
                echo '🧪 Executing BSW Unit Tests: CAN Stack...'
                sh 'make test_can_stack'
            }
        }

        stage('Coverage Analysis (C)') {
            steps {
                echo '📊 Generating C Code Coverage report (gcovr)...'
                sh '''
                    .venv/bin/gcovr -r . \
                        --filter src/app/bcm/ \
                        --xml-pretty \
                        --xml build/c-coverage.xml \
                        --html-details build/c-coverage.html
                '''
            }
        }
        
        stage('Flash ECU (CMM Integration Mock)') {
            steps {
                echo '⚡ Flashing firmware via Mocked CMM runner...'
                sh ".venv/bin/python3 scripts/mock_lauterbach.py ELF_PATH=${FIRMWARE_BINARY}"
            }
        }
        
        stage('Linting (Python)') {
            steps {
                echo '🔍 Running isolated static code analysis (pylint)...'
                sh ".venv/bin/python3 -m pylint test/functional/ scripts/ --fail-under=7.0"
            }
        }
        
        stage('Static Analysis (C)') {
            steps {
                echo '🔍 Checking C source code for security and quality issues (flawfinder)...'
                sh ".venv/bin/flawfinder src/app/bcm/ --minlevel=1"
            }
        }
        
        stage('Quality & Compliance (Axivion Style)') {
            steps {
                echo '🔍 Verifying MISRA-C and Architecture Compliance...'
                sh ".venv/bin/python3 scripts/quality_suite.py"
            }
        }
        
        stage('Run Pytest Suite (Virtual CAN)') {
            steps {
                echo '🧪 Executing automated tests in sandbox...'
                sh '''
                    .venv/bin/python3 -m pytest \
                        test/functional/ \
                        --junitxml=test-results.xml \
                        --cov=test/functional \
                        --cov=scripts \
                        --cov-report=xml:coverage.xml \
                        --cov-report=term \
                        --alluredir=allure-results
                '''
            }
        }
        
        stage('Upload to Polarion (Mock Server)') {
            steps {
                echo '📊 Pushing results to Polarion...'
                sh '''
                    # Start mock server in background
                    .venv/bin/python3 scripts/mock_polarion_server.py &
                    MOCK_SERVER_PID=$!
                    sleep 2
                    
                    # Upload results
                    .venv/bin/python3 scripts/polarion_upload.py \
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
            archiveArtifacts artifacts: 'build/firmware.elf, build/c-coverage.xml, coverage.xml, build/quality-report.html'
            allure includeProperties: false, jdk: '', results: [[path: 'allure-results']]
            
            // Note: In a real Jenkins instance, you would use 'cobertura coberturaReportFile: "build/c-coverage.xml"'
            // to show the coverage bars on the dashboard.
        }
        success {
            echo '✅ Pipeline passed! Virtual ECU verified.'
        }
        failure {
            echo '❌ Pipeline failed.'
        }
    }
}
