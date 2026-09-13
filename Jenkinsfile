pipeline {
    agent { label 'mac-harness' }
    
    environment {
        // Clinical path for Mac Toolchain integration
        PATH = "/Applications/ArmGNUToolchain/15.2.rel1/arm-none-eabi/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:${env.PATH}"
    }

    stages {
        stage('Initialize Environment') {
            steps {
                echo '📦 Preparing HIL Environment...'
                sh '''
                    if [ ! -d ".venv" ]; then python3 -m venv .venv; fi
                    . .venv/bin/activate
                    pip install --upgrade pip
                    pip install -r requirements.txt pytest-metadata
                '''
            }
        }

        stage('Lint & Static Analysis') {
            steps {
                echo '🔍 Linting Python (pylint) and scanning C for unsafe patterns (flawfinder)...'
                sh '''
                    . .venv/bin/activate
                    PYTHONPATH=. pylint scripts tests --disable=all --enable=E,F \
                        --init-hook="import sys; sys.path.insert(0, 'tests/functional')"
                    flawfinder --minlevel=3 --error-level=3 bcm/src firmware/BCM_Firmware/Core/Src
                '''
            }
        }

        stage('Unit Tests & Coverage (C)') {
            steps {
                echo '🧩 Running BCM logic unit tests on the host, with coverage...'
                sh 'make test_unit_coverage'
            }
        }

        stage('Build Firmware') {
            steps {
                echo '🔨 Compiling BCM Firmware...'
                sh 'make -C firmware/BCM_Firmware clean all'
            }
        }

        stage('Flash Hardware') {
            steps {
                echo '⚡ Deploying to Physical Nucleo Board...'
                sh 'chmod +x scripts/deploy_bcm.sh'
                sh './scripts/deploy_bcm.sh'
            }
        }

        stage('Functional & System Tests (HIL)') {
            steps {
                echo '🧪 Executing Industry-Standard HIL Validation...'
                sh '''
                    . .venv/bin/activate
                    pytest tests/functional -s -v --alluredir=allure-results --junitxml=test-results.xml --target=hardware
                '''
            }
        }
    }

    post {
        always {
            echo '📋 Publishing JUnit Results...'
            junit testResults: 'test-results.xml', allowEmptyResults: true

            echo '📊 Capturing Allure Results...'
            allure includeProperties: false, jdk: '', results: [[path: 'allure-results']]

            echo '🗄️ Archiving Build Artifacts...'
            archiveArtifacts artifacts: 'firmware/BCM_Firmware/build/BCM_Firmware.bin, build/c-coverage.xml, build/c-coverage.html', allowEmptyArchive: true
        }
        success {
            echo '✅ HIL Validation PASSED.'
        }
        failure {
            echo '❌ HIL Validation FAILED.'
        }
    }
}
