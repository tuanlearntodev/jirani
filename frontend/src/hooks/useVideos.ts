import { useState, useEffect, useCallback } from 'react';
import { Video } from '../types';
import * as videosApi from '../services/api/videos';

export function useVideos() {
    const [videos, setVideos] = useState<Video[]>([]);

    const refresh = useCallback(async () => {
        setVideos(await videosApi.fetchVideos());
    }, []);

    useEffect(() => { refresh(); }, [refresh]);

    return { videos, refresh, setVideos };
}