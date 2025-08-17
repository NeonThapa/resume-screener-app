// src/App.js (Final, Complete Version)

import React, { useState, useEffect } from 'react';
import './App.css';
import FileUpload from './components/FileUpload';
import ResultsList from './components/ResultsList';
import ProgressBar from './components/ProgressBar';

function App() {
  // State for the actual file objects
  const [jdFile, setJdFile] = useState(null);
  const [resumeFiles, setResumeFiles] = useState([]);
  
  // State to hold the temporary, viewable URLs for the resumes
  const [resumeFileObjects, setResumeFileObjects] = useState({});

  // State to manage the UI (loading, messages, results)
  const [isLoading, setIsLoading] = useState(false);
  const [statusMessage, setStatusMessage] = useState('');
  const [results, setResults] = useState([]);

  // This special "hook" runs automatically whenever the user selects new resume files.
  // Its job is to create the temporary URLs for the "View Resume" button.
  useEffect(() => {
    const newFileObjects = {};
    resumeFiles.forEach(file => {
      // Create a temporary, browser-only URL for each file
      newFileObjects[file.name] = URL.createObjectURL(file);
    });
    setResumeFileObjects(newFileObjects);

    // This is a cleanup function to prevent memory leaks in the browser
    return () => {
      Object.values(newFileObjects).forEach(url => URL.revokeObjectURL(url));
    };
  }, [resumeFiles]); // This effect only re-runs when 'resumeFiles' changes

  // This is the main function that talks to our Python backend
  const handleAnalyze = async () => {
    if (!jdFile || resumeFiles.length === 0) {
      alert("Please upload a Job Description and at least one resume.");
      return;
    }

    setIsLoading(true);
    setResults([]);
    
    // --- Simulated Progress for a better user experience ---
    const messages = ["Parsing resumes...", "Constructing AI prompt...", "Waiting for AI analysis (this can take a moment)..."];
    let messageIndex = 0;
    setStatusMessage(messages[messageIndex]);
    
    const interval = setInterval(() => {
      messageIndex++;
      if (messageIndex < messages.length) {
        setStatusMessage(messages[messageIndex]);
      } else {
        // Stop the interval if the API call is taking a very long time
        clearInterval(interval);
      }
    }, 4000); // Change the message every 4 seconds
    // --- End of Progress Simulation ---

    // Use FormData to package our files for the API call
    const formData = new FormData();
    formData.append('jd', jdFile);
    resumeFiles.forEach(file => {
      formData.append('resumes', file);
    });

    try {
      const response = await fetch('http://127.0.0.1:8000/analyze/', {
        method: 'POST',
        body: formData,
      });

      if (!response.ok) {
        throw new Error(`Server error! status: ${response.status}`);
      }

      const data = await response.json();
      
      if (data.error) {
        throw new Error(data.error);
      }
      
      setResults(data.results);

    } catch (error) {
      console.error("Error analyzing resumes:", error);
      alert(`An error occurred: ${error.message}`);
    } finally {
      // This block runs whether the API call succeeds or fails
      setIsLoading(false);
      clearInterval(interval); // Always stop the message interval
    }
  };

  return (
    <div className="App">
      <header className="App-header">
        <h1 className="title">AI Resume Screener</h1>
        <p className="subtitle">
          Upload a Job Description and a batch of resumes for an AI-powered ranking.
        </p>
      </header>
      
      <main className="main-content">
        {/* This is the main conditional rendering logic for the UI */}

        {/* 1. Show the upload section if we are not loading and have no results */}
        {!isLoading && results.length === 0 && (
          <>
            <FileUpload 
              jdFile={jdFile}
              setJdFile={setJdFile}
              resumeFiles={resumeFiles}
              setResumeFiles={setResumeFiles}
            />
            <div className="button-container">
              <button 
                onClick={handleAnalyze}
                disabled={!jdFile || resumeFiles.length === 0}
                className="analyze-button"
              >
                Analyze Batch
              </button>
            </div>
          </>
        )}

        {/* 2. Show the progress bar if we are currently loading */}
        {isLoading && <ProgressBar message={statusMessage} />}
        
        {/* 3. Show the results list if we are not loading and have results */}
        {!isLoading && results.length > 0 && (
          <ResultsList results={results} fileObjects={resumeFileObjects} />
        )}
        
      </main>
    </div>
  );
}

export default App;