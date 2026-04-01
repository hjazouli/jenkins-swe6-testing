pipeline {
    agent any
    
    stages {
        stage('Checkout') {
            steps {
                // Pulls code from your Git repository into the Jenkins workspace
                checkout scm
                
                sh 'echo "Checkout complete! Looking at files:"'
                sh 'ls -la'
            }
        }
        
        stage('Install Dependencies') {
            steps {
                // Update package manager and install Python tools if they don't exist
                sh 'apt-get update && apt-get install -y python3 python3-pip python3-venv'
                
                // Create a virtual environment and install our test dependencies
                sh 'python3 -m venv venv'
                sh './venv/bin/pip install -r requirements.txt'
            }
        }
        
        stage('Run Tests') {
            steps {
                // Run pytest to execute all functions matching test_* in our test file
                sh './venv/bin/pytest -v test_math_operations.py'
            }
        }
    }
}
