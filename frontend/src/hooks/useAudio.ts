import { useState, useEffect, useCallback } from 'react';
import { Audio } from '../types';
import * as audioApi from '../services/api/audio';

export function useAudio() {
    const [audioTracks, setAudioTracks] = useState<Audio[]>([]);

    const refresh = useCallback(async () => {
        setAudioTracks(await audioApi.fetchAudioTracks());
    }, []);

    useEffect(() => { refresh(); }, [refresh]);

    return { audioTracks, refresh, setAudioTracks };
}