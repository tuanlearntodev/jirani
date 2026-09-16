// src/pages/Setup.tsx
import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { ShieldCheck, ShieldAlert, Loader2 } from 'lucide-react';
import * as setupApi from '../services/api/setup';

type Status = 'loading' | 'success' | 'already-done' | 'error';

const Setup = () => {
    const [status, setStatus] = useState<Status>('loading');
    const [message, setMessage] = useState('');

    useEffect(() => {
        setupApi.runSetup()
            .then(data => {
                setMessage(data.message);
                setStatus('success');
            })
            .catch((e: Error) => {
                if (e.message.toLowerCase().includes('already been revealed')) {
                    setStatus('already-done');
                } else {
                    setMessage(e.message);
                    setStatus('error');
                }
            });
    }, []);

    return (
        <div className="min-h-screen bg-[#FAFAF9] flex items-center justify-center font-sans p-6">
            <div className="w-full max-w-[480px] bg-white rounded-[20px] border border-[#E8E4DE] shadow-[0_4px_24px_rgba(28,26,23,0.07)] p-8 text-center">

                {status === 'loading' && (
                    <div className="flex flex-col items-center gap-3 py-6">
                        <Loader2 size={28} className="animate-spin text-[#B8922A]" />
                        <p className="text-sm text-[#6B6560] m-0">Setting up admin account...</p>
                    </div>
                )}

                {status === 'success' && (
                    <>
                        <div className="w-[52px] h-[52px] rounded-2xl bg-[#F0FAF4] flex items-center justify-center mx-auto mb-3.5">
                            <ShieldCheck size={22} color="#2D7A4F" />
                        </div>
                        <h2 className="text-xl font-bold text-[#1C1A17] mb-2">Admin Account Created</h2>
                        <div className="bg-[#F5EDD8] border-[1.5px] border-[#D4A93A] rounded-2xl px-5 py-4 my-4 text-left">
                            <p className="text-[13px] text-[#1C1A17] m-0 leading-relaxed font-mono break-words">
                                {message}
                            </p>
                        </div>
                        <p className="text-xs text-[#A09890] mb-5 leading-relaxed">
                            Write this down now — this page will not show it again, and setup can only run once.
                        </p>
                        <Link to="/" className="inline-block py-3 px-6 bg-[#B8922A] text-white rounded-xl text-sm font-semibold no-underline">
                            Go to Sign In
                        </Link>
                    </>
                )}

                {status === 'already-done' && (
                    <>
                        <div className="w-[52px] h-[52px] rounded-2xl bg-[#F5EDD8] flex items-center justify-center mx-auto mb-3.5">
                            <ShieldAlert size={22} color="#B8922A" />
                        </div>
                        <h2 className="text-xl font-bold text-[#1C1A17] mb-2">Setup Already Complete</h2>
                        <p className="text-[13px] text-[#6B6560] mb-5 leading-relaxed">
                            The admin account was already created and its credentials have already been shown once.
                            If you've lost them, they can't be re-displayed here.
                        </p>
                        <Link to="/" className="inline-block py-3 px-6 bg-[#F7F5F2] text-[#6B6560] border border-[#E8E4DE] rounded-xl text-sm font-semibold no-underline">
                            Go to Sign In
                        </Link>
                    </>
                )}

                {status === 'error' && (
                    <>
                        <div className="w-[52px] h-[52px] rounded-2xl bg-[#FEF2F0] flex items-center justify-center mx-auto mb-3.5">
                            <ShieldAlert size={22} color="#D94F3D" />
                        </div>
                        <h2 className="text-xl font-bold text-[#1C1A17] mb-2">Setup Failed</h2>
                        <p className="text-[13px] text-[#D94F3D] mb-5 leading-relaxed">{message}</p>
                    </>
                )}
            </div>
        </div>
    );
};

export default Setup;