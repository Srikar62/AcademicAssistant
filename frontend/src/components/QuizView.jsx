import React, { useState } from 'react';
import { generateQuiz } from '../services/api';
import { useToast } from './Toast';

export default function QuizView({ doc, onBack }) {
  const toast = useToast();
  const [quiz, setQuiz] = useState(null);
  const [loading, setLoading] = useState(false);
  const [answers, setAnswers] = useState({});
  const [revealed, setRevealed] = useState({});
  const [submitted, setSubmitted] = useState(false);
  const [numQuestions, setNumQuestions] = useState(5);
  const [topic, setTopic] = useState('');

  const handleGenerate = async () => {
    setLoading(true);
    setQuiz(null);
    setAnswers({});
    setRevealed({});
    setSubmitted(false);

    try {
      const result = await generateQuiz({
        doc_id: doc?.doc_id,
        num_questions: numQuestions,
        topic: topic || undefined,
      });
      setQuiz(result);
    } catch (err) {
      toast.error(`Quiz generation failed: ${err.message}`);
    } finally {
      setLoading(false);
    }
  };

  const selectAnswer = (qIdx, letter) => {
    if (submitted) return;
    setAnswers(prev => ({ ...prev, [qIdx]: letter }));
  };

  const handleSubmit = () => {
    setSubmitted(true);
    const allRevealed = {};
    quiz.questions.forEach((_, i) => { allRevealed[i] = true; });
    setRevealed(allRevealed);
  };

  const score = quiz ? quiz.questions.reduce((acc, q, i) =>
    acc + (answers[i] === q.correct_answer ? 1 : 0), 0
  ) : 0;

  const getOptionLetter = (optionText) => {
    const match = optionText.match(/^([A-D])\)/);
    return match ? match[1] : '';
  };

  return (
    <div className="animate-slide-up">
      <button className="back-btn" onClick={onBack}>← Back to Document</button>

      {/* Config */}
      {!quiz && !loading && (
        <div className="card" style={{ padding: 24, marginBottom: 20 }}>
          <h3 style={{ fontSize: '1.05rem', fontWeight: 600, marginBottom: 16 }}>🧠 Generate Quiz</h3>
          <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap', alignItems: 'flex-end' }}>
            <div>
              <label style={{ fontSize: '0.8rem', color: 'var(--text-muted)', display: 'block', marginBottom: 4 }}>
                Number of Questions
              </label>
              <select
                className="input"
                style={{ width: 100 }}
                value={numQuestions}
                onChange={(e) => setNumQuestions(Number(e.target.value))}
              >
                {[3, 5, 8, 10].map(n => <option key={n} value={n}>{n}</option>)}
              </select>
            </div>
            <div style={{ flex: 1, minWidth: 200 }}>
              <label style={{ fontSize: '0.8rem', color: 'var(--text-muted)', display: 'block', marginBottom: 4 }}>
                Topic (optional)
              </label>
              <input
                className="input"
                placeholder="e.g., neural networks"
                value={topic}
                onChange={(e) => setTopic(e.target.value)}
              />
            </div>
            <button className="btn btn-primary" onClick={handleGenerate}>
              Generate Quiz
            </button>
          </div>
        </div>
      )}

      {/* Loading */}
      {loading && (
        <div className="loading-overlay">
          <div className="spinner spinner-lg" />
          <span>Generating quiz questions…</span>
        </div>
      )}

      {/* Quiz */}
      {quiz && (
        <div className="card" style={{ padding: 24 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20 }}>
            <h3 style={{ fontSize: '1.05rem', fontWeight: 600 }}>
              🧠 Quiz {quiz.topic ? `— ${quiz.topic}` : ''}
            </h3>
            {!submitted && (
              <button
                className="btn btn-primary"
                onClick={handleSubmit}
                disabled={Object.keys(answers).length === 0}
              >
                Submit Answers
              </button>
            )}
          </div>

          {/* Score */}
          {submitted && (
            <div className="quiz-score" style={{ marginBottom: 24 }}>
              <div className="quiz-score-value">{score}/{quiz.questions.length}</div>
              <div className="quiz-score-label">
                {score === quiz.questions.length ? '🎉 Perfect score!' :
                 score >= quiz.questions.length * 0.7 ? '👏 Great job!' :
                 'Keep studying!'}
              </div>
            </div>
          )}

          {/* Questions */}
          {quiz.questions.map((q, qIdx) => (
            <div key={qIdx} className="quiz-question">
              <div className="quiz-question-text">
                <span className="quiz-question-number">Q{qIdx + 1}.</span>
                {q.question}
              </div>
              <div className="quiz-options">
                {q.options.map((opt, oIdx) => {
                  const letter = getOptionLetter(opt) || String.fromCharCode(65 + oIdx);
                  const isSelected = answers[qIdx] === letter;
                  const isCorrect = letter === q.correct_answer;
                  const qRevealed = revealed[qIdx];

                  let cls = 'quiz-option';
                  if (qRevealed) {
                    cls += ' disabled';
                    if (isCorrect) cls += ' correct';
                    else if (isSelected && !isCorrect) cls += ' incorrect';
                  } else if (isSelected) {
                    cls += ' selected';
                  }

                  return (
                    <button
                      key={oIdx}
                      className={cls}
                      onClick={() => selectAnswer(qIdx, letter)}
                    >
                      {opt}
                    </button>
                  );
                })}
              </div>
              {isRevealed(qIdx) && q.explanation && (
                <div className="quiz-explanation">
                  <strong>Explanation:</strong> {q.explanation}
                  {q.source_label && (
                    <span className="badge badge-accent" style={{ marginLeft: 8 }}>
                      {q.source_label}
                    </span>
                  )}
                </div>
              )}
            </div>
          ))}

          {submitted && (
            <div style={{ textAlign: 'center', marginTop: 16 }}>
              <button className="btn btn-secondary" onClick={() => { setQuiz(null); }}>
                Generate New Quiz
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );

  function isRevealed(idx) { return !!revealed[idx]; }
}
