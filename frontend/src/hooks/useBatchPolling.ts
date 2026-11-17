import { useEffect, useReducer, useRef } from 'react'
import { getBatch } from '../api.ts'
import type { Batch } from '../types.ts'

const TERMINAL = new Set(['completed', 'completed_with_errors'])
const POLL_MS   = 1000
const MAX_ERRORS = 3

// ── State managed by a reducer so every update is a single dispatch ────────

type State = { batch: Batch | null; error: string | null }
type Action =
  | { type: 'SET_BATCH';  batch: Batch }
  | { type: 'SET_ERROR';  error: string }
  | { type: 'RESET' }

const INIT: State = { batch: null, error: null }

function reducer(_state: State, action: Action): State {
  switch (action.type) {
    case 'SET_BATCH':  return { batch: action.batch, error: null }
    case 'SET_ERROR':  return { batch: null, error: action.error }
    case 'RESET':      return INIT
  }
}

export interface UseBatchPollingResult {
  batch: Batch | null
  error: string | null
}

// ── Hook ───────────────────────────────────────────────────────────────────

export function useBatchPolling(batchId: string | null): UseBatchPollingResult {
  const [state, dispatch] = useReducer(reducer, INIT)

  // Ref to cancel in-flight timers and detect stale closures.
  const cancelledRef  = useRef(false)
  const timerRef      = useRef<ReturnType<typeof setTimeout> | null>(null)
  const errorCountRef = useRef(0)

  useEffect(() => {
    cancelledRef.current  = false
    errorCountRef.current = 0

    // Clear any previous timer.
    if (timerRef.current !== null) {
      clearTimeout(timerRef.current)
      timerRef.current = null
    }

    if (!batchId) {
      // Dispatch the reset as a micro-task so the setState is async.
      const id = setTimeout(() => dispatch({ type: 'RESET' }), 0)
      return () => {
        cancelledRef.current = true
        clearTimeout(id)
      }
    }

    const poll = async (): Promise<void> => {
      if (cancelledRef.current) return
      try {
        const result = await getBatch(batchId)
        if (cancelledRef.current) return
        errorCountRef.current = 0
        dispatch({ type: 'SET_BATCH', batch: result })
        if (!TERMINAL.has(result.status)) {
          timerRef.current = setTimeout(poll, POLL_MS)
        }
      } catch (err) {
        if (cancelledRef.current) return
        errorCountRef.current += 1
        if (errorCountRef.current >= MAX_ERRORS) {
          const msg = err instanceof Error ? err.message : 'Polling failed.'
          dispatch({ type: 'SET_ERROR', error: msg })
        } else {
          timerRef.current = setTimeout(poll, POLL_MS)
        }
      }
    }

    timerRef.current = setTimeout(poll, 0)

    return () => {
      cancelledRef.current = true
      if (timerRef.current !== null) {
        clearTimeout(timerRef.current)
        timerRef.current = null
      }
    }
  }, [batchId])

  return state
}
