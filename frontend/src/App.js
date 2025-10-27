// src/App.js (LLM progress-aware version)

import React, { useState, useEffect, useRef } from 'react';
import './App.css';
import FileUpload from './components/FileUpload';
import ResultsList from './components/ResultsList';
import ProgressBar from './components/ProgressBar';
import JDOverview from './components/JDOverview';
import tataStriveLogo from './assets/tata-strive-logo.png';

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
  const [jdSections, setJdSections] = useState({});
  const [progressInfo, setProgressInfo] = useState(null);

  const statusIntervalRef = useRef(null);
  const progressIntervalRef = useRef(null);

  // This special "hook" runs automatically whenever the user selects new resume files.
  // Its job is to create the temporary URLs for the "View Resume" button.
  useEffect(() => {
    const newFileObjects = {};
    resumeFiles.forEach((file) => {
      // Create a temporary, browser-only URL for each file
      newFileObjects[file.name] = URL.createObjectURL(file);
    });
    setResumeFileObjects(newFileObjects);

    // This is a cleanup function to prevent memory leaks in the browser
    return () => {
      Object.values(newFileObjects).forEach((url) => URL.revokeObjectURL(url));
    };
  }, [resumeFiles]); // This effect only re-runs when 'resumeFiles' changes

  const clearActiveIntervals = () => {
    if (statusIntervalRef.current) {
      clearInterval(statusIntervalRef.current);
      statusIntervalRef.current = null;
    }
    if (progressIntervalRef.current) {
      clearInterval(progressIntervalRef.current);
      progressIntervalRef.current = null;
    }
  };

  const startProgressPolling = (jobToken, estimatedTotal) => {
    if (!jobToken) {
      return;
    }

    const stopProgressPolling = () => {
      if (progressIntervalRef.current) {
        clearInterval(progressIntervalRef.current);
        progressIntervalRef.current = null;
      }
    };

    const apiBase = (process.env.REACT_APP_API_URL || 'http://127.0.0.1:8000/analyze/').replace(
      /\/analyze\/?$/,
      ''
    );

    const poll = async () => {
      try {
        const response = await fetch(`${apiBase}/progress/${jobToken}`);
        if (response.status === 404) {
          return;
        }
        if (!response.ok) {
          return;
        }
        const data = await response.json();
        setProgressInfo({
          current: data.current || '',
          processed: data.processed || 0,
          total: data.total || estimatedTotal || resumeFiles.length,
          done: Boolean(data.done),
        });
        if (data.done) {
          stopProgressPolling();
        }
      } catch (err) {
        // Ignore transient polling errors; the main request will surface issues if needed.
      }
    };

    poll();
    progressIntervalRef.current = setInterval(poll, 2200);
  };

  // This is the main function that talks to our Python backend
  const handleAnalyze = async () => {
    const mode = 'llm';
    const engine = 'ai';
    if (!jdFile || resumeFiles.length === 0) {
      alert('Please upload a Job Description and at least one resume.');
      return;
    }

    clearActiveIntervals();
    setIsLoading(true);
    setResults([]);

    const messages = [
      "We're priming the job description for the language model. This can take a few minutes - feel free to grab a coffee.",
      'The LLM is reading each resume end-to-end. Sit tight while we crunch the details.',
      "We're compiling ranked insights and interview prompts from the LLM analysis.",
    ];
    let messageIndex = 0;
    setStatusMessage(messages[messageIndex]);
    statusIntervalRef.current = setInterval(() => {
      messageIndex += 1;
      if (messageIndex < messages.length) {
        setStatusMessage(messages[messageIndex]);
      } else {
        clearInterval(statusIntervalRef.current);
        statusIntervalRef.current = null;
      }
    }, 4000);
    // --- End of Progress Simulation ---

    const generatedJobId = window.crypto?.randomUUID?.() ?? `job-${Date.now()}`;
    setProgressInfo({
      current: '',
      processed: 0,
      total: resumeFiles.length,
      done: false,
    });

    // Use FormData to package our files for the API call
    const formData = new FormData();
    formData.append('jd', jdFile);
    formData.append('mode', mode);
    formData.append('engine', engine);
    formData.append('job_id', generatedJobId);
    resumeFiles.forEach((file) => {
      formData.append('resumes', file);
    });

    startProgressPolling(generatedJobId, resumeFiles.length);

    try {
      const response = await fetch(process.env.REACT_APP_API_URL || 'http://127.0.0.1:8000/analyze/', {
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
      setJdSections(data.jd_sections || {});
      setProgressInfo({
        current: '',
        processed: (data.results || []).length,
        total: (data.results || []).length,
        done: true,
      });
    } catch (error) {
      console.error('Error analyzing resumes:', error);
      alert(`An error occurred: ${error.message}`);
    } finally {
      // This block runs whether the API call succeeds or fails
      setIsLoading(false);
      clearActiveIntervals(); // Always stop the message interval and polling
      setTimeout(() => setProgressInfo(null), 800);
    }
  };

  const handleReset = () => {
    if (isLoading) {
      return;
    }
    setJdFile(null);
    setResumeFiles([]);
    setResumeFileObjects({});
    setResults([]);
    setJdSections({});
    setStatusMessage('');
    setProgressInfo(null);
    clearActiveIntervals();
  };

  const progressDetail = (() => {
    if (!progressInfo) {
      return 'Hang tight while we process the uploaded files—feel free to grab a quick break.';
    }
    if (progressInfo.done) {
      return 'Analysis complete. Preparing ranked results...';
    }
    return 'Hang tight while we process the uploaded files—feel free to grab a quick break.';
  })();

  return (
    <div className="app-shell">
      <header className="brand-bar">
        <div className="brand-identity">
          <img src={tataStriveLogo} alt="TATA Strive logo" className="brand-logo" />
          <div className="brand-copy">
            <span className="brand-title">TATA STRIVE</span>
            <span className="brand-subtitle">HR Talent Intelligence Desk</span>
          </div>
        </div>
        <div className="brand-badge">
          <span>Empowering Employability</span>
        </div>
      </header>

      <section className="hero-banner">
        <div className="hero-copy">
          <h1>Precision Screening for Strategic Hiring</h1>
          <p>
            Merge Tata Strive's purpose-driven workforce philosophy with data-assisted resume intelligence.
            Upload a JD, add resumes, and receive a transparent ranking with actionable insights.
          </p>
          <ul className="hero-highlights">
            <li>Weighted scoring aligned to Tata Strive capability frameworks</li>
            <li>Instant visibility into matched and missing competencies</li>
            <li>AI-backed summaries to support HR partner conversations</li>
          </ul>
        </div>
      </section>

      <main className="workspace">
        <section className="panel upload-panel">
          <div className="panel-header">
            <h2>Upload Inputs</h2>
            <p>Use the Tata Strive JD template and add candidate resumes exported from PDF or DOCX.</p>
          </div>
          <FileUpload
            jdFile={jdFile}
            setJdFile={setJdFile}
            resumeFiles={resumeFiles}
            setResumeFiles={setResumeFiles}
          />
          <div className="cta-row">
            <button
              onClick={handleAnalyze}
              disabled={!jdFile || resumeFiles.length === 0 || isLoading}
              className="analyze-button"
            >
              Run Deep Screening
            </button>
            <button
              type="button"
              onClick={handleReset}
              disabled={isLoading || (!jdFile && resumeFiles.length === 0 && results.length === 0)}
              className="analyze-button ghost"
            >
              Reset
            </button>
            <p className="cta-hint">
              Supported files: PDF, DOCX. Text is extracted locally before the LLM scores each resume.
            </p>
          </div>
        </section>

        {Object.keys(jdSections).length > 0 && <JDOverview sections={jdSections} />}
      </main>

      <section className="results-hub">
        {isLoading && <ProgressBar message={statusMessage} detail={progressDetail} />}
        {!isLoading && results.length === 0 && (
          <div className="empty-state">
            <h3>No analysis yet</h3>
            <p>
              Upload a job description and candidate resumes to generate a prioritized shortlist with insights
              for Tata Strive's HR leadership.
            </p>
          </div>
        )}
        {!isLoading && results.length > 0 && (
          <ResultsList results={results} fileObjects={resumeFileObjects} />
        )}
      </section>
    </div>
  );
}

export default App;
