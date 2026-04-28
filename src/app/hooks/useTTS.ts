'use client'

import { useState, useCallback } from 'react'
import { pythonBridge } from '@/lib/python-bridge'
import { useToast } from '@/components/toast'

export interface UseTTSReturn {
  isSpeaking: boolean
  generatingMessageIndex: number | null
  currentAudio: HTMLAudioElement | null
  speakMessage: (content: string, messageIndex: number, voice?: string) => Promise<void>
  stopSpeaking: () => void
}

export function useTTS(): UseTTSReturn {
  const [isSpeaking, setIsSpeaking] = useState(false)
  const [generatingMessageIndex, setGeneratingMessageIndex] = useState<number | null>(null)
  const [currentAudio, setCurrentAudio] = useState<HTMLAudioElement | null>(null)
  const { showToast } = useToast()

  const stopSpeaking = useCallback(() => {
    if (currentAudio) {
      currentAudio.pause()
      currentAudio.currentTime = 0
    }
    setCurrentAudio(null)
    setIsSpeaking(false)
    setGeneratingMessageIndex(null)
  }, [currentAudio])

  const speakMessage = useCallback(async (content: string, messageIndex: number, voice?: string) => {
    if (isSpeaking || generatingMessageIndex !== null) {
      stopSpeaking()
      return
    }

    try {
      setGeneratingMessageIndex(messageIndex)
      const blob = await pythonBridge.tts.generateSpeech({
        input: content,
        voice: voice || 'af_bella',
        speed: 1.0
      })
      setGeneratingMessageIndex(null)
      setIsSpeaking(true)
      const url = URL.createObjectURL(blob)
      const audio = new Audio(url)

      audio.onended = () => {
        setIsSpeaking(false)
        URL.revokeObjectURL(url)
        setCurrentAudio(null)
      }

      audio.onerror = (e) => {
        console.error('Audio playback error:', e)
        setIsSpeaking(false)
        URL.revokeObjectURL(url)
        setCurrentAudio(null)
      }

      setCurrentAudio(audio)
      await audio.play()
    } catch (error) {
      console.error('TTS error:', error)
      const errorMessage = error instanceof Error ? error.message : 'Unknown error'
      showToast(`TTS failed: ${errorMessage}`, 'error')
      setGeneratingMessageIndex(null)
      setIsSpeaking(false)
    }
  }, [isSpeaking, generatingMessageIndex, stopSpeaking])

  return {
    isSpeaking,
    generatingMessageIndex,
    currentAudio,
    speakMessage,
    stopSpeaking,
  }
}
