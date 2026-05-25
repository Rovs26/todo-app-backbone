/**
 * Fetches current weather and precipitation probability for the user's
 * location using the Open-Meteo API (free, no API key required).
 *
 * Returns a small reactive state object.  The fetch is only triggered once
 * (lazy) and the result is cached in module scope so repeated calls don't
 * re-request.
 */

import { ref } from 'vue'

export interface WeatherInfo {
  /** Short human-readable description, e.g. "Partly cloudy, 22 °C" */
  summary: string
  /** 0-100 chance of precipitation in the current hour */
  precipChance: number
  /** Temperature in Celsius */
  tempC: number
  /** WMO weather code (https://open-meteo.com/en/docs#weathervariables) */
  weatherCode: number
  /** City name if available from reverse-geocoding */
  city: string | null
}

// Module-level cache so multiple composable calls share the same request.
let _cached: WeatherInfo | null = null
let _promise: Promise<WeatherInfo | null> | null = null

const WMO_LABELS: Record<number, string> = {
  0: 'Clear sky', 1: 'Mainly clear', 2: 'Partly cloudy', 3: 'Overcast',
  45: 'Foggy', 48: 'Icy fog', 51: 'Light drizzle', 53: 'Drizzle',
  55: 'Heavy drizzle', 61: 'Light rain', 63: 'Rain', 65: 'Heavy rain',
  71: 'Light snow', 73: 'Snow', 75: 'Heavy snow', 80: 'Rain showers',
  81: 'Heavy showers', 82: 'Violent showers', 95: 'Thunderstorm',
  96: 'Thunderstorm with hail', 99: 'Heavy thunderstorm',
}

function wmoLabel(code: number): string {
  return WMO_LABELS[code] ?? 'Unknown'
}

async function getPosition(): Promise<{ lat: number; lon: number } | null> {
  if (typeof navigator === 'undefined' || !navigator.geolocation) return null
  return new Promise((resolve) => {
    navigator.geolocation.getCurrentPosition(
      (pos) => resolve({ lat: pos.coords.latitude, lon: pos.coords.longitude }),
      () => resolve(null),
      { timeout: 5000 },
    )
  })
}

async function fetchWeather(): Promise<WeatherInfo | null> {
  const pos = await getPosition()
  if (!pos) return null

  const url =
    `https://api.open-meteo.com/v1/forecast` +
    `?latitude=${pos.lat}&longitude=${pos.lon}` +
    `&current=temperature_2m,weather_code,precipitation_probability` +
    `&forecast_days=1&timezone=auto`

  try {
    const res = await fetch(url)
    if (!res.ok) return null
    const data = await res.json()
    const cur = data.current ?? {}
    const tempC = Math.round(cur.temperature_2m ?? 0)
    const weatherCode = cur.weather_code ?? 0
    const precipChance = cur.precipitation_probability ?? 0

    // Best-effort city lookup (nominatim, no key).
    let city: string | null = null
    try {
      const geo = await fetch(
        `https://nominatim.openstreetmap.org/reverse?lat=${pos.lat}&lon=${pos.lon}&format=json`,
        { headers: { Accept: 'application/json' } },
      )
      if (geo.ok) {
        const geoData = await geo.json()
        city =
          geoData.address?.city ||
          geoData.address?.town ||
          geoData.address?.village ||
          null
      }
    } catch {
      // city stays null
    }

    const label = wmoLabel(weatherCode)
    const summary = city
      ? `${label}, ${tempC}°C in ${city}`
      : `${label}, ${tempC}°C`

    return { summary, precipChance, tempC, weatherCode, city }
  } catch {
    return null
  }
}

export function useWeather() {
  const weather = ref<WeatherInfo | null>(null)
  const loading = ref(false)
  const error = ref(false)

  async function load() {
    if (_cached) {
      weather.value = _cached
      return
    }
    if (!_promise) {
      _promise = fetchWeather()
    }
    loading.value = true
    error.value = false
    try {
      const result = await _promise
      _cached = result
      weather.value = result
    } catch {
      error.value = true
    } finally {
      loading.value = false
    }
  }

  /**
   * Returns a contextual hint string when weather is relevant to a time-
   * sensitive todo (e.g. "going out later", "grocery run").  Returns null
   * when weather is fine or not available.
   */
  function getHint(text: string): string | null {
    if (!weather.value) return null
    const { precipChance, tempC, weatherCode, summary } = weather.value

    // Only surface a hint if the todo seems time-sensitive / outdoor.
    const isOutdoor = /\b(go|going|out|outside|walk|run|shop|store|market|grocery|pick up|later|today|this (morning|afternoon|evening|evening)|trip)\b/i.test(text)
    if (!isOutdoor) return null

    if (precipChance >= 50) {
      return `☔ ${summary} — bring an umbrella, ${precipChance}% chance of rain.`
    }
    if (precipChance >= 20) {
      return `🌦️ ${summary} — light chance of rain (${precipChance}%).`
    }
    if (tempC >= 35) {
      return `🌡️ ${summary} — stay hydrated, it's very hot out!`
    }
    if (tempC <= 0) {
      return `🥶 ${summary} — dress warmly, it's freezing!`
    }
    if (weatherCode === 0 || weatherCode === 1) {
      return `☀️ ${summary} — great weather for getting out!`
    }
    return null
  }

  return { weather, loading, error, load, getHint }
}
