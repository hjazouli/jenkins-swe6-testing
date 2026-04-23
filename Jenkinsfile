pipeline {
    agent any 
    
    triggers {
        pollSCM('* * * * *') // Poll for changes every minute
    }

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
                    source .venv/bin/activate
                    pip install --upgrade pip
                    pip install pytest pyserial allure-pytest pytest-metadata
                '''
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
        
        stage('HIL Verification') {
            steps {
                echo '🧪 Executing Industry-Standard HIL Validation...'
                sh '''
                    source .venv/bin/activate
                    pytest tests/functional -s -v --alluredir=allure-results --target=hardware
                '''
            }
        }
    }
    
    post {
        always {
            echo '📊 Capturing Allure Results...'
            allure includeProperties: false, jdk: '', results: [[path: 'allure-results']]
            
            echo '🗄️ Archiving Build Artifacts...'
            archiveArtifacts artifacts: 'firmware/BCM_Firmware/build/BCM_Firmware.bin', allowEmptyArchive: true
        }
        success {
            echo '✅ HIL Validation PASSED.'
        }
        failure {
            echo '❌ HIL Validation FAILED.'
        }
    }
}
