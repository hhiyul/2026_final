import React, { useState } from 'react';
import axios from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL;

if (!API_BASE_URL) {
    console.warn('VITE_API_BASE_URL이 설정되지 않았습니다.');
}

const api = axios.create({ baseURL: API_BASE_URL });

const getImageUrl = (thumbnailUrl) => {
    if (!thumbnailUrl) return '';
    if (thumbnailUrl.startsWith('http://') || thumbnailUrl.startsWith('https://')) return thumbnailUrl;
    return `${API_BASE_URL}${thumbnailUrl}`;
};

function App() {
    const [userId, setUserId] = useState('test_user');
    const [file, setFile] = useState(null);
    const [query, setQuery] = useState('쿨톤 스트릿하게');
    const [password, setPassword] = useState('');
    const [garmentsList, setGarmentsList] = useState([]);
    const [recommendResults, setRecommendResults] = useState([]);
    const [jsonResponse, setJsonResponse] = useState(null);
    const [loading, setLoading] = useState(false);
    const [selectedItem, setSelectedItem] = useState(null);
    const [selectedIndex, setSelectedIndex] = useState(-1);
    const [detailItems, setDetailItems] = useState([]);
    const [deleteTarget, setDeleteTarget] = useState(null);
    const [deletePassword, setDeletePassword] = useState('');

    const openDetail = (item, index, items) => {
        setSelectedItem(item);
        setSelectedIndex(index);
        setDetailItems(items);
    };

    const closeDetail = () => {
        setSelectedItem(null);
        setSelectedIndex(-1);
        setDetailItems([]);
    };

    const handlePrev = () => {
        if (selectedIndex <= 0) return;
        const nextIndex = selectedIndex - 1;
        setSelectedIndex(nextIndex);
        setSelectedItem(detailItems[nextIndex]);
    };

    const handleNext = () => {
        if (selectedIndex < 0 || selectedIndex >= detailItems.length - 1) return;
        const nextIndex = selectedIndex + 1;
        setSelectedIndex(nextIndex);
        setSelectedItem(detailItems[nextIndex]);
    };

    const handleCreateUser = async () => {
        if (!userId.trim()) {
            alert('User ID를 입력하세요.');
            return;
        }

        if (password.length < 8) {
            alert('비밀번호는 8자 이상 입력하세요.');
            return;
        }

        setLoading(true);

        try {
            const res = await api.post('/users', {
                user_id: userId.trim(),
                password,
            });

            setJsonResponse(res.data);
            alert('사용자 등록 완료!');
        } catch (err) {
            console.error(err);
            alert('사용자 등록 실패: ' + (err.response?.data?.detail || err.message));
        } finally {
            setLoading(false);
        }
    };

    const openDeleteModal = (item) => {
        setDeleteTarget(item);
        setDeletePassword('');
    };

    const closeDeleteModal = () => {
        if (loading) return;
        setDeleteTarget(null);
        setDeletePassword('');
    };

    const handleDeleteGarment = async () => {
        if (!deleteTarget) return;

        if (!deletePassword) {
            alert('비밀번호를 입력하세요.');
            return;
        }

        setLoading(true);

        try {
            const res = await api.delete(`/garments/${deleteTarget.garment_id}`, {
                data: {
                    user_id: userId,
                    password: deletePassword,
                },
            });

            setJsonResponse(res.data);

            setGarmentsList((prev) =>
                prev.filter((item) => item.garment_id !== deleteTarget.garment_id)
            );
            setRecommendResults((prev) =>
                prev.filter((item) => item.garment_id !== deleteTarget.garment_id)
            );

            if (selectedItem?.garment_id === deleteTarget.garment_id) {
                closeDetail();
            }

            setDeleteTarget(null);
            setDeletePassword('');
            alert('옷이 삭제되었습니다.');
        } catch (err) {
            console.error(err);
            alert('삭제 실패: ' + (err.response?.data?.detail || err.message));
        } finally {
            setLoading(false);
        }
    };

    const handleGetGarments = async (showLoading = true) => {
        if (showLoading) setLoading(true);
        try {
            const res = await api.get('/garments', { params: { user_id: userId } });
            setGarmentsList(res.data.items || []);
            setJsonResponse(res.data);
        } catch (err) {
            console.error(err);
            alert('조회 실패: ' + (err.response?.data?.detail || err.message));
        } finally {
            if (showLoading) setLoading(false);
        }
    };

    const handleRegister = async () => {
        if (!file) return alert('이미지 파일을 선택하세요.');
        setLoading(true);
        const formData = new FormData();
        formData.append('user_id', userId);
        formData.append('file', file);
        try {
            const res = await api.post('/garments', formData);
            setJsonResponse(res.data);
            alert('옷 등록 성공!');
            await handleGetGarments(false);
        } catch (err) {
            console.error(err);
            alert('옷 등록 실패: ' + (err.response?.data?.detail || err.message));
        } finally {
            setLoading(false);
        }
    };

    const handleRecommend = async () => {
        setLoading(true);
        try {
            const res = await api.post('/recommend', { user_id: userId, query, top_k: 5 });
            setRecommendResults(res.data.results || []);
            setJsonResponse(res.data);
            closeDetail();
        } catch (err) {
            console.error(err);
            alert('추천 실패: ' + (err.response?.data?.detail || err.message));
        } finally {
            setLoading(false);
        }
    };

    return (
        <div style={{ maxWidth: '800px', margin: '0 auto', padding: '20px', fontFamily: 'sans-serif' }}>
            <h1>Fashion AI 테스트</h1>

            <section style={{ border: '1px solid #ccc', padding: '15px', borderRadius: '8px', marginBottom: '20px' }}>
                <h3>0. 사용자 등록 (POST /users)</h3>

                <input
                    type="text"
                    value={userId}
                    onChange={(e) => setUserId(e.target.value)}
                    placeholder="User ID"
                    style={{ width: '100%', padding: '8px', marginBottom: '10px', boxSizing: 'border-box' }}
                />

                <input
                    type="password"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    placeholder="비밀번호 (8자 이상)"
                    style={{ width: '100%', padding: '8px', marginBottom: '10px', boxSizing: 'border-box' }}
                />

                <button
                    onClick={handleCreateUser}
                    disabled={loading}
                    style={{ width: '100%', padding: '10px', background: '#0f766e', color: '#fff', border: 'none', borderRadius: '4px', cursor: 'pointer' }}
                >
                    {loading ? '처리 중...' : '사용자 등록'}
                </button>
            </section>

            <section style={{ border: '1px solid #ccc', padding: '15px', borderRadius: '8px', marginBottom: '20px' }}>
                <h3>1. 옷 등록 (POST /garments)</h3>
                <input type="text" value={userId} onChange={(e) => setUserId(e.target.value)} placeholder="User ID"
                       style={{ width: '100%', padding: '8px', marginBottom: '10px', boxSizing: 'border-box' }} />
                <input type="file" accept="image/*" onChange={(e) => setFile(e.target.files?.[0] || null)} style={{ marginBottom: '10px' }} />
                <br />
                <button onClick={handleRegister} disabled={loading}
                        style={{ width: '100%', padding: '10px', background: '#2563eb', color: '#fff', border: 'none', borderRadius: '4px', cursor: 'pointer' }}>
                    {loading ? '처리 중...' : '옷 등록 및 임베딩 저장'}
                </button>
            </section>

            <section style={{ border: '1px solid #ccc', padding: '15px', borderRadius: '8px', marginBottom: '20px' }}>
                <h3>2. 코디 추천 (POST /recommend)</h3>
                <input type="text" value={query} onChange={(e) => setQuery(e.target.value)} placeholder="추천 쿼리 (예: 쿨톤 스트릿하게)"
                       style={{ width: '100%', padding: '8px', marginBottom: '10px', boxSizing: 'border-box' }} />
                <button onClick={handleRecommend} disabled={loading}
                        style={{ width: '100%', padding: '10px', background: '#2563eb', color: '#fff', border: 'none', borderRadius: '4px', cursor: 'pointer' }}>
                    {loading ? '추천 중...' : '추천 요청'}
                </button>
            </section>

            <section style={{ border: '1px solid #ccc', padding: '15px', borderRadius: '8px', marginBottom: '20px' }}>
                <h3>3. 내 전체 옷장 조회 (GET /garments)</h3>
                <button onClick={() => handleGetGarments(true)} disabled={loading}
                        style={{ width: '100%', padding: '10px', background: '#4b5563', color: '#fff', border: 'none', borderRadius: '4px', cursor: 'pointer' }}>
                    {loading ? '불러오는 중...' : '옷장 불러오기'}
                </button>

                {garmentsList.length > 0 && (
                    <div style={{ display: 'flex', gap: '12px', flexWrap: 'wrap', marginTop: '15px' }}>
                        {garmentsList.map((item, idx) => (
                            <div
                                key={item.garment_id}
                                onClick={() => openDetail(item, idx, garmentsList)}
                                style={{
                                    border: '1px solid #ddd',
                                    borderRadius: '6px',
                                    padding: '8px',
                                    textAlign: 'center',
                                    cursor: 'pointer',
                                    boxShadow: '0 2px 4px rgba(0,0,0,0.08)',
                                }}
                            >
                                <img
                                    src={getImageUrl(item.thumbnail_url)}
                                    alt={item.category}
                                    style={{ width: '110px', height: '110px', objectFit: 'cover', borderRadius: '4px' }}
                                />
                                <p style={{ margin: '5px 0 0', fontSize: '13px', fontWeight: 'bold' }}>
                                    {item.category}
                                </p>
                            </div>
                        ))}
                    </div>
                )}
            </section>

            <section style={{ border: '1px solid #ccc', padding: '15px', borderRadius: '8px' }}>
                <h3>🖼️ 추천 결과 이미지 뷰어</h3>
                {recommendResults.length === 0 ? (
                    <p style={{ color: '#ef4444' }}>추천 결과가 없습니다. 옷을 먼저 등록한 뒤 추천을 요청하세요.</p>
                ) : (
                    <div style={{ display: 'flex', gap: '15px', flexWrap: 'wrap' }}>
                        {recommendResults.map((item, idx) => (
                            <div key={item.garment_id || idx} onClick={() => openDetail(item, idx, recommendResults)}
                                 style={{ border: '1px solid #ddd', padding: '10px', borderRadius: '6px', textAlign: 'center', cursor: 'pointer', boxShadow: '0 2px 4px rgba(0,0,0,0.1)' }}>
                                <img src={getImageUrl(item.thumbnail_url)} alt={item.category}
                                     style={{ width: '130px', height: '130px', objectFit: 'cover', borderRadius: '4px' }} />
                                <p style={{ fontSize: '14px', fontWeight: 'bold', margin: '5px 0' }}>{item.category}</p>
                                <p style={{ fontSize: '12px', color: '#2563eb', margin: 0 }}>Score: {item.score}</p>
                            </div>
                        ))}
                    </div>
                )}

                <h4 style={{ marginTop: '20px' }}>📋 Response JSON</h4>
                <pre style={{ background: '#f3f4f6', padding: '10px', borderRadius: '4px', overflowX: 'auto', fontSize: '12px' }}>
          {JSON.stringify(jsonResponse, null, 2)}
        </pre>
            </section>

            {selectedItem && (
                <div onClick={closeDetail}
                     style={{ position: 'fixed', top: 0, left: 0, right: 0, bottom: 0, backgroundColor: 'rgba(0, 0, 0, 0.6)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000 }}>
                    <div onClick={(e) => e.stopPropagation()}
                         style={{ background: '#fff', padding: '25px', borderRadius: '12px', maxWidth: '450px', width: '90%', boxShadow: '0 10px 25px rgba(0,0,0,0.3)', position: 'relative' }}>
                        <button onClick={closeDetail}
                                style={{ position: 'absolute', top: '15px', right: '15px', border: 'none', background: 'transparent', fontSize: '20px', cursor: 'pointer', fontWeight: 'bold' }}>✕</button>

                        <h2 style={{ marginTop: 0, color: '#1e293b' }}>🔍 의류 상세 정보</h2>
                        <div style={{ textAlign: 'center', margin: '15px 0' }}>
                            <img src={getImageUrl(selectedItem.thumbnail_url)} alt={selectedItem.category}
                                 style={{ width: '100%', maxHeight: '280px', objectFit: 'contain', borderRadius: '8px', border: '1px solid #f1f5f9' }} />
                        </div>

                        <table style={{ width: '100%', fontSize: '14px', borderCollapse: 'collapse', marginTop: '10px' }}>
                            <tbody>
                            <tr><td style={{ padding: '6px', fontWeight: 'bold', color: '#64748b' }}>카테고리</td><td style={{ padding: '6px', fontWeight: 'bold', color: '#2563eb' }}>{selectedItem.category}</td></tr>
                            {selectedItem.rank != null && selectedItem.score != null && (
                                <tr>
                                    <td style={{ padding: '6px', fontWeight: 'bold', color: '#64748b' }}>유사도 랭킹 / 스코어</td>
                                    <td style={{ padding: '6px' }}>{selectedItem.rank}위 / {selectedItem.score}</td>
                                </tr>
                            )}
                            {selectedItem.conf != null && (
                                <tr>
                                    <td style={{ padding: '6px', fontWeight: 'bold', color: '#64748b' }}>검출 신뢰도</td>
                                    <td style={{ padding: '6px' }}>{(selectedItem.conf * 100).toFixed(1)}%</td>
                                </tr>
                            )}
                            {selectedItem.created_at && <tr><td style={{ padding: '6px', fontWeight: 'bold', color: '#64748b' }}>등록일시</td><td style={{ padding: '6px', fontSize: '12px' }}>{selectedItem.created_at}</td></tr>}
                            </tbody>
                        </table>

                        <div style={{ display: 'flex', gap: '10px', marginTop: '20px' }}>
                            <button onClick={handlePrev} disabled={selectedIndex <= 0} style={{ flex: 1, padding: '10px', cursor: selectedIndex <= 0 ? 'not-allowed' : 'pointer' }}>이전</button>
                            <button onClick={closeDetail} style={{ flex: 1, padding: '10px', cursor: 'pointer' }}>닫기</button>
                            <button onClick={handleNext} disabled={selectedIndex >= detailItems.length - 1}
                                    style={{ flex: 1, padding: '10px', cursor: selectedIndex >= detailItems.length - 1 ? 'not-allowed' : 'pointer' }}>다음</button>
                        </div>

                        <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: '12px' }}>
                            <button
                                onClick={() => openDeleteModal(selectedItem)}
                                disabled={loading}
                                style={{
                                    padding: '6px 10px',
                                    background: '#fff',
                                    color: '#dc2626',
                                    border: '1px solid #dc2626',
                                    borderRadius: '6px',
                                    cursor: 'pointer',
                                    fontSize: '12px',
                                    fontWeight: 'bold',
                                }}
                            >
                                삭제
                            </button>
                        </div>
                    </div>
                </div>
            )}

            {deleteTarget && (
                <div
                    onClick={closeDeleteModal}
                    style={{
                        position: 'fixed',
                        top: 0,
                        left: 0,
                        right: 0,
                        bottom: 0,
                        backgroundColor: 'rgba(0, 0, 0, 0.55)',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        zIndex: 1100,
                    }}
                >
                    <div
                        onClick={(e) => e.stopPropagation()}
                        style={{
                            background: '#fff',
                            width: '90%',
                            maxWidth: '360px',
                            borderRadius: '12px',
                            padding: '24px',
                            boxShadow: '0 12px 30px rgba(0,0,0,0.25)',
                        }}
                    >
                        <h3 style={{ marginTop: 0, marginBottom: '8px' }}>옷 삭제</h3>
                        <p style={{ marginTop: 0, color: '#64748b', fontSize: '14px' }}>
                            삭제하려면 사용자 비밀번호를 입력하세요.
                        </p>

                        <div style={{ display: 'flex', gap: '12px', alignItems: 'center', margin: '16px 0' }}>
                            <img
                                src={getImageUrl(deleteTarget.thumbnail_url)}
                                alt={deleteTarget.category}
                                style={{
                                    width: '72px',
                                    height: '72px',
                                    objectFit: 'cover',
                                    borderRadius: '8px',
                                    border: '1px solid #e2e8f0',
                                }}
                            />
                            <div>
                                <div style={{ fontWeight: 'bold' }}>{deleteTarget.category}</div>
                                <div style={{ color: '#94a3b8', fontSize: '12px', marginTop: '4px' }}>
                                    {deleteTarget.garment_id}
                                </div>
                            </div>
                        </div>

                        <input
                            type="password"
                            value={deletePassword}
                            onChange={(e) => setDeletePassword(e.target.value)}
                            onKeyDown={(e) => {
                                if (e.key === 'Enter' && !loading) handleDeleteGarment();
                            }}
                            placeholder="비밀번호"
                            autoFocus
                            style={{
                                width: '100%',
                                boxSizing: 'border-box',
                                padding: '10px',
                                border: '1px solid #cbd5e1',
                                borderRadius: '6px',
                                marginBottom: '14px',
                            }}
                        />

                        <div style={{ display: 'flex', gap: '10px', justifyContent: 'flex-end' }}>
                            <button
                                onClick={closeDeleteModal}
                                disabled={loading}
                                style={{
                                    padding: '9px 14px',
                                    background: '#fff',
                                    color: '#334155',
                                    border: '1px solid #cbd5e1',
                                    borderRadius: '6px',
                                    cursor: 'pointer',
                                }}
                            >
                                취소
                            </button>

                            <button
                                onClick={handleDeleteGarment}
                                disabled={loading || !deletePassword}
                                style={{
                                    padding: '9px 14px',
                                    background: '#dc2626',
                                    color: '#fff',
                                    border: 'none',
                                    borderRadius: '6px',
                                    cursor: loading || !deletePassword ? 'not-allowed' : 'pointer',
                                    opacity: loading || !deletePassword ? 0.6 : 1,
                                }}
                            >
                                {loading ? '삭제 중...' : '삭제'}
                            </button>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
}

export default App;
