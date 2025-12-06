import { useState } from 'react';

interface HelloResponse {
  message: string;
  timestamp: string;
}

interface EchoResponse {
  echo: Record<string, unknown>;
  receivedAt: string;
}

interface ApiInfo {
  name: string;
  version: string;
  status: string;
  timestamp: string;
}

const API_BASE = '/api/hello-fastify';

function App() {
  const [name, setName] = useState('World');
  const [helloResponse, setHelloResponse] = useState<HelloResponse | null>(null);
  const [echoInput, setEchoInput] = useState('{"message": "Hello from frontend!"}');
  const [echoResponse, setEchoResponse] = useState<EchoResponse | null>(null);
  const [apiInfo, setApiInfo] = useState<ApiInfo | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const fetchApiInfo = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(API_BASE);
      const data = await res.json();
      setApiInfo(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch API info');
    } finally {
      setLoading(false);
    }
  };

  const fetchHello = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${API_BASE}/hello?name=${encodeURIComponent(name)}`);
      const data = await res.json();
      setHelloResponse(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch hello');
    } finally {
      setLoading(false);
    }
  };

  const fetchEcho = async () => {
    setLoading(true);
    setError(null);
    try {
      const body = JSON.parse(echoInput);
      const res = await fetch(`${API_BASE}/echo`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
      const data = await res.json();
      setEchoResponse(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch echo');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-gray-100 py-8 px-4">
      <div className="max-w-2xl mx-auto">
        <h1 className="text-4xl font-bold text-center text-blue-600 mb-8">
          Hello Fastify
        </h1>

        {error && (
          <div className="bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded mb-4">
            {error}
          </div>
        )}

        {/* API Info Section */}
        <section className="bg-white rounded-lg shadow-md p-6 mb-6">
          <h2 className="text-xl font-semibold mb-4">API Info</h2>
          <button
            onClick={fetchApiInfo}
            disabled={loading}
            className="bg-blue-500 hover:bg-blue-600 text-white font-medium py-2 px-4 rounded disabled:opacity-50"
          >
            {loading ? 'Loading...' : 'Get API Info'}
          </button>
          {apiInfo && (
            <pre className="mt-4 bg-gray-50 p-4 rounded overflow-x-auto text-sm">
              {JSON.stringify(apiInfo, null, 2)}
            </pre>
          )}
        </section>

        {/* Hello Section */}
        <section className="bg-white rounded-lg shadow-md p-6 mb-6">
          <h2 className="text-xl font-semibold mb-4">Hello Endpoint</h2>
          <div className="flex gap-2 mb-4">
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Enter your name"
              className="flex-1 border border-gray-300 rounded px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
            <button
              onClick={fetchHello}
              disabled={loading}
              className="bg-green-500 hover:bg-green-600 text-white font-medium py-2 px-4 rounded disabled:opacity-50"
            >
              Say Hello
            </button>
          </div>
          {helloResponse && (
            <pre className="bg-gray-50 p-4 rounded overflow-x-auto text-sm">
              {JSON.stringify(helloResponse, null, 2)}
            </pre>
          )}
        </section>

        {/* Echo Section */}
        <section className="bg-white rounded-lg shadow-md p-6 mb-6">
          <h2 className="text-xl font-semibold mb-4">Echo Endpoint</h2>
          <textarea
            value={echoInput}
            onChange={(e) => setEchoInput(e.target.value)}
            placeholder="Enter JSON to echo"
            rows={3}
            className="w-full border border-gray-300 rounded px-3 py-2 mb-4 font-mono text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
          <button
            onClick={fetchEcho}
            disabled={loading}
            className="bg-purple-500 hover:bg-purple-600 text-white font-medium py-2 px-4 rounded disabled:opacity-50"
          >
            Send Echo
          </button>
          {echoResponse && (
            <pre className="mt-4 bg-gray-50 p-4 rounded overflow-x-auto text-sm">
              {JSON.stringify(echoResponse, null, 2)}
            </pre>
          )}
        </section>

        {/* Available Endpoints */}
        <section className="bg-white rounded-lg shadow-md p-6">
          <h2 className="text-xl font-semibold mb-4">Available Endpoints</h2>
          <ul className="space-y-2 font-mono text-sm">
            <li className="flex">
              <span className="bg-blue-100 text-blue-800 px-2 py-1 rounded mr-2">GET</span>
              <span>/api/hello-fastify</span>
            </li>
            <li className="flex">
              <span className="bg-green-100 text-green-800 px-2 py-1 rounded mr-2">GET</span>
              <span>/api/hello-fastify/hello?name=World</span>
            </li>
            <li className="flex">
              <span className="bg-purple-100 text-purple-800 px-2 py-1 rounded mr-2">POST</span>
              <span>/api/hello-fastify/echo</span>
            </li>
          </ul>
        </section>
      </div>
    </div>
  );
}

export default App;
