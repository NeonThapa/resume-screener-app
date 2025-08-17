import React from 'react';
import CandidateCard from './CandidateCard';
import './ResultsList.css';

// The component now accepts 'fileObjects' as a prop
function ResultsList({ results, fileObjects }) {
  return (
    <div className="results-container">
      <h2>Analysis Results</h2>
      {results.map((candidate) => (
        <CandidateCard 
          key={candidate.rank} 
          candidate={candidate} 
          // Look up the correct URL using the candidate's filename
          // and pass it down as the 'fileUrl' prop.
          fileUrl={fileObjects[candidate.filename]}
        />
      ))}
    </div>
  );
}

export default ResultsList;