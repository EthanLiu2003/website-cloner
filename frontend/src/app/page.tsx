'use client'
import { useState } from "react";
import { useEffect } from "react";

export default function Home() {
  const[url, setUrl] = useState('');
  const[isValidUrl, setIsValidUrl] = useState(null);
  const[isLoading, setIsLoading] = useState(false);
  const[jobId, setJobId] = useState('');
  const[errorState, setErrorState] = useState('');
  const[responseData, setResponseData] = useState(null);
  const[jobStatus, setJobStatus] = useState(null);
  useEffect(() => {
  if (jobId && jobStatus?.status !== 'completed' && jobStatus?.status !== 'error') {
    const interval = setInterval(async () => {
      try {
        const response = await fetch(`http://localhost:8000/api/status/${jobId}`);
        const data = await response.json();
        console.log("Job status update:", data);
        setJobStatus(data);
        
        if (data.status === 'completed' || data.status === 'error') {
          clearInterval(interval);
        }
      } catch (error) {
        console.error('Failed to check job status:', error);
      }
    }, 2000);

    return () => clearInterval(interval);
  }
}, [jobId, jobStatus?.status]);
  const handleClick = async () => {
    console.log("Button clicked");
    if(!url) {
      console.log("Input is null");
      alert("Please enter a url!");
      return
    } else {
      console.log("Input is not null");
    }
    let isValid = false;
    try {
      new URL(url);
      isValid = true;
    }catch (error) {
      isValid = false;
    }
    setIsValidUrl(isValid);
    if (isValid) {
      setIsLoading(true);
      setErrorState('');
      setJobStatus(null);
      setResponseData(null);
      try{
        const response = await fetch('http://localhost:8000/api/clone', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({url: url}),
        });
        const data = await response.json();
        console.log("Backend response:", data);
        setJobId(data.job_id);
        setResponseData(data)
      }catch(error) {
        setErrorState('Failed to start cloning: ' + error.message);
      } finally {
        setIsLoading(false);
      }
      } else {
        alert("Invalid URL format")
      }
    };
  return (
    <div>
      <h1>Website Cloner</h1>
      <input 
        value = {url}
        type ="url"
        placeholder="type url here"
        onChange={e => setUrl(e.target.value)}
        />
      <button 
        onClick={handleClick}
        style = {{cursor: 'pointer'}}
      >Clone!</button>
      {!url && <p>Empty URL!</p>}
      {isValidUrl === false && <p>Invalid URL</p> }
      {jobId && (
        <div style={{marginTop: '20px', padding: '10px', border:'1px solid #ccc'}}>
          <h3>Job Started!</h3>
          <p><strong>Job ID:</strong> {jobId}</p>
          <p><strong>Current Status:</strong> {jobStatus?.status || responseData?.status || 'Unknown'}</p>
          {jobStatus?.progress && (
            <p><strong>Progress:</strong> {jobStatus.progress}%</p>
          )}
          {jobStatus?.message && (
            <p><strong>Message:</strong> {jobStatus.message}</p>
          )}
          {jobStatus?.error && (
            <p style={{color: 'red'}}><strong>Error:</strong> {jobStatus.error}</p>
          )}
            {jobStatus?.status === 'completed' && jobStatus?.result_url && (
              <p>
                <strong>Cloned website:</strong>{' '}
                <a 
                  href={`http://localhost:8000${jobStatus.result_url}`} 
                  target="_blank" 
                  rel="noopener noreferrer"
                  style={{color: 'blue', textDecoration: 'underline'}}
                >
                  View here
                </a>
              </p>
            )}
          
          <details style={{marginTop: '10px'}}>
            <summary>Debug Info (click to expand)</summary>
            <pre style={{fontSize: '12px'}}>{JSON.stringify(jobStatus || responseData, null, 2)}</pre>
          </details>
        </div>
      )}
    </div>
  );

}

