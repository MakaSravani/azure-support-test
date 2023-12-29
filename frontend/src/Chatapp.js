

import React, { useState } from 'react';
import axios from 'axios';
import './ChatApp.css';

const ChatApp = () => {
  const [userQuestion, setUserQuestion] = useState('');
  const [conversation, setConversation] = useState([]);

  const handleAskQuestion = async () => {
    try {
      // const response = await axios.post('http://localhost:8000/', { user_question: userQuestion });
      const response = await axios.post('https://studious-acorn-v6vpqj66wjw63xwjq-5000.app.github.dev/', { user_question: userQuestion });
      const { user_question, assistant_response } = response.data;

      // Append the new message to the conversation
      setConversation((prevConversation) => [
        ...prevConversation,
        { role: 'user', content: user_question },
        { role: 'assistant', content: assistant_response },
      ]);

      // Clear the user input
      setUserQuestion('');
    } catch (error) {
      console.error('Error asking question:', error.message);
    }
  };

  return (
    <div className="chat-container">
        <div className="headings">
        <h3>Deerfield HR Gen AI Chatbot</h3>
        <h4>Powered by JustAskAthena.ai from eAlliance</h4>
      </div>
      <div className="conversation">
      
        <h2>Ask Anything about Deerfield HR</h2>
        {conversation.map((message, index) => (
          <div key={index} className={message.role === 'user' ? 'user-message' : 'assistant-message'}>
            {message.content}
          </div>
        ))}
      </div>
      <div className="user-input">
        <input
          type="text"
          id="user-question"
          placeholder="Type your question..."
          value={userQuestion}
          onChange={(e) => setUserQuestion(e.target.value)}
        />
        <button onClick={handleAskQuestion}>Ask</button>
      </div>
    </div>
  );
};

export default ChatApp;
