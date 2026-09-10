import React, { useState } from 'react';
import axios from 'axios';

function App() {
    const [userId, setUserId] = useState('test_user');
    const [file, setFile] = useState(null);
    const [query, setQuery] = useState('쿨톤 스트릿하게');

    const [garmentsList, setGarmentsList] = useState([]);
    const [recommendResults, setRecommendResults] = useState([]);
    const [jsonResponse, setJsonResponse] = useState(null);
    const [loading, setLoading] = useState(false);

    // 💡 선택된 이미지 모달 상세 보기 상태
    const [selectedItem, setSelectedItem] = useState(null);

    // 1. 옷 등록 (POST /garments)
    const handleRegister = async () => {
        if (!file) return alert('이미지 파일을 선택하세요.');
        setLoading(true);
        const formData = new FormData();
        formData.append('user_id', userId);
        formData.append('file', file);

        try {
            const res = await axios.post('/garments', formData);
            setJsonResponse(res.data);
            alert('옷 등록 성공!');
        } catch (err) {
            console.error(err);
            alert('옷 등록 실패: ' + (err.response?.data?.detail || err.message));
        } finally {
            setLoading(false);
        }
    };

    // 2. 코디 추천 (POST /recommend)
    const handleRecommend = async () => {
        setLoading(true);
        try {
            const res = await axios.post('/recommend', {
                user_id: userId,
                query: query,
                top_k: 5
            });
            setRecommendResults(res.data.results || []);
            setJsonResponse(res.data);
        } catch (err) {
            console.error(err);
            alert('추천 실패: ' + (err.response?.data?.detail || err.message));
        } finally {
            setLoading(false);
        }
    };

    // 3. 내 전체 옷장 조회 (GET /garments)
    const handleGetGarments = async () => {
        setLoading(true);
        try {
            const res = await axios.get(`/garments?user_id=${userId}`);
            setGarmentsList(res.data.items || []);
            setJsonResponse(res.data);
        } catch (err) {
            console.error(err);
            alert('조회 실패: ' + (err.response?.data?.detail || err.message));
        } finally {
            setLoading(false);
        }
    };

    return (
        <div style={{ maxWidth: '800px', margin: '0 auto', padding: '20px', fontFamily: 'sans-serif' }}>
            <h1>테스트</h1>

            {/* 1. 옷 등록 */}
            <section style={{ border: '1px solid #ccc', padding: '15px', borderRadius: '8px', marginBottom: '20px' }}>
                <h3>1. 옷 등록 (POST /garments)</h3>
                <input
                    type="text"
                    value={userId}
                    onChange={(e) => setUserId(e.target.value)}
                    placeholder="User ID"
                    style={{ width: '100%', padding: '8px', marginBottom: '10px' }}
                />
                <input
                    type="file"
                    onChange={(e) => setFile(e.target.files[0])}
                    style={{ marginBottom: '10px' }}
                />
                <br />
                <button
                    onClick={handleRegister}
                    disabled={loading}
                    style={{ width: '100%', padding: '10px', background: '#2563eb', color: '#fff', border: 'none', borderRadius: '4px', cursor: 'pointer' }}
                >
                    {loading ? '처리 중...' : '옷 등록 및 임베딩 저장'}
                </button>
            </section>

            {/* 2. 코디 추천 */}
            <section style={{ border: '1px solid #ccc', padding: '15px', borderRadius: '8px', marginBottom: '20px' }}>
                <h3>2. 코디 추천 (POST /recommend)</h3>
                <input
                    type="text"
                    value={query}
                    onChange={(e) => setQuery(e.target.value)}
                    placeholder="추천 쿼리 (예: 쿨톤 스트릿하게)"
                    style={{ width: '100%', padding: '8px', marginBottom: '10px' }}
                />
                <button
                    onClick={handleRecommend}
                    disabled={loading}
                    style={{ width: '100%', padding: '10px', background: '#2563eb', color: '#fff', border: 'none', borderRadius: '4px', cursor: 'pointer' }}
                >
                    {loading ? '추천 중...' : '추천 요청'}
                </button>
            </section>

            {/* 3. 전체 옷장 조회 */}
            <section style={{ border: '1px solid #ccc', padding: '15px', borderRadius: '8px', marginBottom: '20px' }}>
                <h3>3. 내 전체 옷장 조회 (GET /garments)</h3>
                <button
                    onClick={handleGetGarments}
                    disabled={loading}
                    style={{ width: '100%', padding: '10px', background: '#4b5563', color: '#fff', border: 'none', borderRadius: '4px', cursor: 'pointer' }}
                >
                    {loading ? '불러오는 중...' : '옷장 불러오기'}
                </button>
            </section>

            {/* 결과 이미지 뷰어 */}
            <section style={{ border: '1px solid #ccc', padding: '15px', borderRadius: '8px' }}>
                <h3>🖼️ 결과 이미지 뷰어 (클릭하여 상세 보기)</h3>
                {recommendResults.length === 0 ? (
                    <p style={{ color: '#ef4444' }}>추천 결과가 없습니다. 옷을 먼저 등록했는지 확인하세요.</p>
                ) : (
                    <div style={{ display: 'flex', gap: '15px', flexWrap: 'wrap' }}>
                        {recommendResults.map((item, idx) => (
                            <div
                                key={idx}
                                onClick={() => setSelectedItem(item)} // 💡 이미지 카드를 클릭하면 상세 모달 오픈
                                style={{
                                    border: '1px solid #ddd',
                                    padding: '10px',
                                    borderRadius: '6px',
                                    textAlign: 'center',
                                    cursor: 'pointer',
                                    transition: 'transform 0.2s, box-shadow 0.2s',
                                    boxShadow: '0 2px 4px rgba(0,0,0,0.1)'
                                }}
                            >
                                <img src={item.thumbnail_url} alt={item.category} style={{ width: '130px', height: '130px', objectFit: 'cover', borderRadius: '4px' }} />
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

            {/* 💡 상세 정보 모달 팝업 컴포넌트 */}
            {selectedItem && (
                <div
                    onClick={() => setSelectedItem(null)} // 바깥 배경 클릭 시 닫힘
                    style={{
                        position: 'fixed',
                        top: 0,
                        left: 0,
                        right: 0,
                        bottom: 0,
                        backgroundColor: 'rgba(0, 0, 0, 0.6)',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        zIndex: 1000
                    }}
                >
                    <div
                        onClick={(e) => e.stopPropagation()} // 모달 내부 클릭 시 닫힘 방지
                        style={{
                            background: '#fff',
                            padding: '25px',
                            borderRadius: '12px',
                            maxWidth: '450px',
                            width: '90%',
                            boxShadow: '0 10px 25px rgba(0,0,0,0.3)',
                            position: 'relative'
                        }}
                    >
                        <button
                            onClick={() => setSelectedItem(null)}
                            style={{
                                position: 'absolute',
                                top: '15px',
                                right: '15px',
                                border: 'none',
                                background: 'transparent',
                                fontSize: '20px',
                                cursor: 'pointer',
                                fontWeight: 'bold'
                            }}
                        >
                            ✕
                        </button>

                        <h2 style={{ marginTop: 0, color: '#1e293b' }}>🔍 의류 상세 정보</h2>
                        <div style={{ textAlign: 'center', margin: '15px 0' }}>
                            <img
                                src={selectedItem.thumbnail_url}
                                alt={selectedItem.category}
                                style={{ width: '100%', maxHeight: '280px', objectFit: 'contain', borderRadius: '8px', border: '1px solid #f1f5f9' }}
                            />
                        </div>

                        <table style={{ width: '100%', fontSize: '14px', borderCollapse: 'collapse', marginTop: '10px' }}>
                            <tbody>
                            <tr>
                                <td style={{ padding: '6px', fontWeight: 'bold', color: '#64748b' }}>카테고리</td>
                                <td style={{ padding: '6px', fontWeight: 'bold', color: '#2563eb' }}>{selectedItem.category}</td>
                            </tr>
                            <tr>
                                <td style={{ padding: '6px', fontWeight: 'bold', color: '#64748b' }}>유사도 랭킹 / 스코어</td>
                                <td style={{ padding: '6px' }}>{selectedItem.rank}위 / {selectedItem.score}</td>
                            </tr>
                            {selectedItem.created_at && (
                                <tr>
                                    <td style={{ padding: '6px', fontWeight: 'bold', color: '#64748b' }}>등록일시</td>
                                    <td style={{ padding: '6px', fontSize: '12px' }}>{selectedItem.created_at}</td>
                                </tr>
                            )}
                            </tbody>
                        </table>
                        {/* 넘기는 기능 */}
                        <button
                            onClick={(e) => { e.stopPropagation(); handleNext(); }}
                            disabled={selectedIndex === recommendResults.length - 1}
                            style={{
                                position: 'absolute',
                                right: '20px',
                                background: 'rgba(255, 255, 255, 0.8)',
                                border: 'none',
                                borderRadius: '50%',
                                width: '50px',
                                height: '50px',
                                fontSize: '28px',
                                cursor: selectedIndex === recommendResults.length - 1 ? 'not-allowed' : 'pointer',
                                opacity: selectedIndex === recommendResults.length - 1 ? 0.3 : 1,
                                zIndex: 1001,
                                display: 'flex',
                                alignItems: 'center',
                                justifyContent: 'center'
                            }}
                        >
                            닫기
                        </button>
                    </div>
                </div>
            )}
        </div>
    );
}

export default App;