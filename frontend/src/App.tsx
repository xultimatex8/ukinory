function App() {
  return (
    <main className="flex min-h-screen items-center justify-center bg-gray-950">
      <div className="text-center">
        <div className="mx-auto mb-6 flex h-20 w-20 items-center justify-center rounded-2xl bg-purple-600">
          <span className="text-3xl font-bold text-white">U</span>
        </div>

        <h1 className="text-4xl font-bold text-white">
          Ukinory
        </h1>

        <p className="mt-3 text-gray-400">
          Your movie journey starts here.
        </p>

        <div className="mt-8 flex justify-center gap-3">
          <span className="rounded-full bg-white/10 px-4 py-2 text-sm text-gray-300">
            React
          </span>
          <span className="rounded-full bg-white/10 px-4 py-2 text-sm text-gray-300">
            Django
          </span>
          <span className="rounded-full bg-white/10 px-4 py-2 text-sm text-gray-300">
            PostgreSQL
          </span>
        </div>
      </div>
    </main>
  )
}

export default App