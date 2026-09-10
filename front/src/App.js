import { useState } from 'react';
import { motion } from 'framer-motion'; // 아까 추천한 애니메이션 라이브러리
import { FaShoppingCart, FaTrash } from 'react-icons/fa'; // 아이콘 라이브러리

function App() {
    // 💡 단일 파일에서 '배열(Array)' 상태로 변경하여 여러 장을 관리합니다.
    const [selectedFiles, setSelectedFiles] = useState([]);
    const [loading, setLoading] = useState(false);
    const [result, setResult] = useState(null);

    const [isModalOpen, setIsModalOpen] = useState(false);
    const [showDetail, setShowDetail] = useState(false);
    const [zoomedImage, setZoomedImage] = useState(null);

    // 💡 여러 개의 파일을 선택했을 때 처리하는 함수
    const handleFileChange = (event) => {
        const files = Array.from(event.target.files);

        // 기존에 선택된 사진들에 새로 추가된 사진들을 이어 붙입니다.
        // 각 파일 객체에 미리보기용 임시 URL(preview)을 생성해서 함께 저장합니다.
        const fileWithPreviews = files.map(file => ({
            fileObject: file,
                previewUrl: URL.createObjectURL(file)
        }));

        setSelectedFiles([...selectedFiles, ...fileWithPreviews]);
    };

    // 💡 선택한 사진 중 특정 사진을 제외하고 싶을 때 지우는 함수
    const removeFile = (indexToRemove) => {
        // 메모리 누수 방지를 위해 생성했던 임시 URL을 해제합니다.
        URL.revokeObjectURL(selectedFiles[indexToRemove].previewUrl);

        setSelectedFiles(selectedFiles.filter((_, index) => index !== indexToRemove));
    };

    const handleSubmit = async (event) => {
        event.preventDefault();
        if (selectedFiles.length === 0) return alert("최소 한 장 이상의 옷 사진을 선택해주세요!");

        setLoading(true);
        const formData = new FormData();

        // 💡 여러 장의 파일을 FormData 상자에 모두 담아줍니다.
        selectedFiles.forEach((fileItem) => {
            formData.append("files", fileItem.fileObject);
        });

        try {
            // 백엔드로 다중 파일 전송
            const response = await fetch("http://localhost:8080/infer", {
                method: "POST",
                body: formData,
            });

            if (!response.ok) throw new Error("서버 에러");

            const data = await response.json();
            setResult(data);
            setIsModalOpen(true);

        } catch (error) {
            console.error(error);
            alert("분석 실패");
        } finally {
            setLoading(false);
        }
    };

    const goToDetail = () => {
        setIsModalOpen(false);
        setShowDetail(true);
    };

    const resetApp = () => {
        // 앱 리셋 시 임시 URL들을 전부 메모리에서 해제해줍니다.
        selectedFiles.forEach(item => URL.revokeObjectURL(item.previewUrl));
        setSelectedFiles([]);
        setResult(null);
        setShowDetail(false);
        setIsModalOpen(false);
    };

    // ==========================================
    // 3️⃣ 상세 페이지 화면
    // ==========================================
    if (showDetail && result) {
        const searchKeyword = encodeURIComponent(result.prediction);
        const shopUrl = `https://www.musinsa.com/search/musinsa/integration?q=${searchKeyword}`;

        return (
            <div style={{ padding: '40px 20px', maxWidth: '1000px', margin: '0 auto', fontFamily: '"Urbanist", sans-serif', color: '#1a1a1a' }}>

                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '40px' }}>
                    <h2 style={{ fontSize: '32px', fontWeight: '700', margin: 0 }}>세부사항</h2>
                    <button onClick={resetApp} style={{ padding: '10px 20px', cursor: 'pointer', border: '1px solid #ddd', borderRadius: '30px', backgroundColor: 'white', fontWeight: '600' }}>
                        새로 고치기
                    </button>
                </div>

                <div style={{ display: 'grid', gridTemplateColumns: '1fr 300px', gap: '40px', alignItems: 'start' }}>
                    {/* 왼쪽: 이미지 썸네일 & 분석 텍스트 */}
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '30px' }}>

                        {/* 💡 썸네일(작은 사진) 리스트 */}
                        <div>
                            <h3 style={{ fontSize: '18px', marginBottom: '15px' }}>등록한 아이템 (클릭하여 확대)</h3>
                            <div style={{ display: 'flex', gap: '15px', overflowX: 'auto', paddingBottom: '10px' }}>
                                {selectedFiles.map((item, index) => (
                                    <img
                                        key={index}
                                        src={item.previewUrl}
                                        alt={`thumbnail-${index}`}
                                        onClick={() => setZoomedImage(item.previewUrl)} // 💡 클릭 시 해당 이미지를 확대 상태로 설정
                                        style={{
                                            width: '120px', height: '120px', objectFit: 'cover',
                                            borderRadius: '12px', cursor: 'pointer', border: '1px solid #e5e7eb',
                                            transition: 'transform 0.2s'
                                        }}
                                        onMouseOver={(e) => e.currentTarget.style.transform = 'scale(1.05)'}
                                        onMouseOut={(e) => e.currentTarget.style.transform = 'scale(1)'}
                                    />
                                ))}
                            </div>
                        </div>

                        {/* AI 분석 결과 */}
                        <div style={{ backgroundColor: '#f9fafb', padding: '30px', borderRadius: '24px' }}>
                            <h3 style={{ fontSize: '24px', marginBottom: '20px' }}>AI 스타일링 제안</h3>
                            <p style={{ fontSize: '16px', lineHeight: '1.6', color: '#4b5563', marginBottom: '25px' }}>
                                인식된 <strong>{result.prediction}</strong> 아이템은 현재 고객님의 체형 데이터와 가장 조화로운 실루엣을 만들어냅니다.
                            </p>
                            <div style={{ display: 'flex', gap: '15px' }}>
                                <div style={{ flex: 1, backgroundColor: 'white', padding: '15px', borderRadius: '15px', textAlign: 'center' }}>
                                    <span style={{ fontSize: '14px', color: '#9ca3af' }}>AI 신뢰도</span>
                                    <div style={{ fontSize: '22px', fontWeight: 'bold', color: '#10b981' }}>{(result.confidence * 100).toFixed(1)}%</div>
                                </div>
                                <div style={{ flex: 1, backgroundColor: 'white', padding: '15px', borderRadius: '15px', textAlign: 'center' }}>
                                    <span style={{ fontSize: '14px', color: '#9ca3af' }}>추천 톤</span>
                                    <div style={{ fontSize: '18px', fontWeight: 'bold', color: '#3b82f6' }}>#Daily #Fit</div> {/* 데일리 핏은 하드코딩 상태라 추후 수정바람*/}
                                </div>
                            </div>
                        </div>
                    </div>

                    {/* 오른쪽: 쇼핑 버튼 영역 */}
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '15px', position: 'sticky', top: '40px' }}>
                        <h4 style={{ margin: '0 0 10px 5px' }}>바로 구매하기</h4>
                        <a href={shopUrl} target="_blank" rel="noopener noreferrer" style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '12px', padding: '20px', backgroundColor: '#000', color: '#fff', textDecoration: 'none', borderRadius: '18px', fontWeight: '700', fontSize: '16px' }}>
                            <FaShoppingCart size={20} />
                            무신사 추천 상품
                        </a>
                        <button style={{ padding: '20px', borderRadius: '18px', border: '1px solid #000', backgroundColor: 'transparent', fontWeight: '700', cursor: 'pointer' }}>
                            결과 공유하기
                        </button>
                    </div>
                </div>

                {/* ==========================================
            💡 팝업: 이미지 크게 보기 (Lightbox)
            ========================================== */}
                {zoomedImage && (
                    <div
                        style={{
                            position: 'fixed', top: 0, left: 0, width: '100vw', height: '100vh',
                            backgroundColor: 'rgba(0,0,0,0.85)', zIndex: 9999,
                            display: 'flex', justifyContent: 'center', alignItems: 'center'
                        }}
                        onClick={() => setZoomedImage(null)} // 💡 어두운 배경을 누르면 닫힘
                    >
                        {/* 확대된 이미지 */}
                        <img
                            src={zoomedImage}
                            alt="Zoomed"
                            style={{ maxWidth: '90%', maxHeight: '90%', objectFit: 'contain', borderRadius: '10px' }}
                            onClick={(e) => e.stopPropagation()} // 이미지를 클릭했을 때는 닫히지 않도록 이벤트 전파 방지
                        />
                        {/* 닫기 버튼 (우측 상단 X) */}
                        <button
                            onClick={() => setZoomedImage(null)}
                            style={{ position: 'absolute', top: '30px', right: '40px', background: 'none', border: 'none', color: 'white', fontSize: '40px', cursor: 'pointer' }}
                        >
                            &times;
                        </button>
                    </div>
                )}

            </div>
        );
    }

    // ==========================================
    // 1️⃣ 메인 화면 (업로드 및 미리보기 부)
    // ==========================================
    return (
        <div style={{ padding: '50px', maxWidth: '600px', margin: '0 auto', fontFamily: 'sans-serif' }}>
            <h1>     AI 코디 추천 시스템</h1>
            <p>가지고 계신 옷 사진들을 한꺼번에 올려보세요!</p>

            <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
                {/* 💡 multiple 속성을 넣어야 여러 장 선택이 가능해집니다 */}
                <input type="file" accept="image/*" multiple onChange={handleFileChange} style={{ padding: '10px', border: '1px solid #ccc', borderRadius: '5px' }} />

                {/* 💡 사진 미리보기 격자판(Grid) 공간 */}
                {selectedFiles.length > 0 && (
                    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '15px', padding: '15px', border: '1px dashed #aaa', borderRadius: '10px' }}>
                        {selectedFiles.map((item, index) => (
                            <div key={index} style={{ position: 'relative', width: '100%', paddingTop: '100%' }}>
                                <img
                                    src={item.previewUrl}
                                    alt="preview"
                                    style={{ position: 'absolute', top: 0, left: 0, width: '100%', height: '100%', objectFit: 'cover', borderRadius: '8px' }}
                                />
                                {/* 개별 사진 삭제 버튼 */}
                                <button
                                    type="button"
                                    onClick={() => removeFile(index)}
                                    style={{ position: 'absolute', top: '5px', right: '5px', backgroundColor: 'rgba(255,0,0,0.8)', color: 'white', border: 'none', borderRadius: '50%', width: '24px', height: '24px', cursor: 'pointer', display: 'flex', justifyContent: 'center', alignItems: 'center' }}
                                >
                                    <FaTrash size={12} />
                                </button>
                            </div>
                        ))}
                    </div>
                )}

                <button type="submit" disabled={loading} style={{ padding: '15px', backgroundColor: '#007BFF', color: 'white', border: 'none', borderRadius: '5px', cursor: 'pointer', fontSize: '16px', fontWeight: 'bold' }}>
                    {loading ? "AI가 여러 장의 이미지를 교차 분석 중..." : `${selectedFiles.length}장의 코디 추천받기`}
                </button>
            </form>

            {/* 2️⃣ 팝업 모달 */}
            {isModalOpen && result && (
                <div style={{ position: 'fixed', top: 0, left: 0, right: 0, bottom: 0, backgroundColor: 'rgba(0,0,0,0.6)', display: 'flex', justifyContent: 'center', alignItems: 'center', zIndex: 1000 }}>
                    <motion.div
                        initial={{ opacity: 0, scale: 0.9 }}
                        animate={{ opacity: 1, scale: 1 }}
                        transition={{ duration: 0.3 }}
                        style={{ backgroundColor: 'white', padding: '30px', borderRadius: '24px', textAlign: 'center', minWidth: '320px', maxWidth: '400px', boxShadow: '0 10px 30px rgba(0,0,0,0.2)' }}
                    >
                        <h2 style={{ margin: '0 0 20px 0', fontSize: '22px' }}>✨ 분석 완료!</h2>

                        {/* 💡 업로드한 이미지 작게 보여주기 (최대 3장까지만 표기) */}
                        <div style={{ display: 'flex', justifyContent: 'center', gap: '10px', marginBottom: '20px' }}>
                            {selectedFiles.slice(0, 3).map((item, index) => (
                                <img
                                    key={index}
                                    src={item.previewUrl}
                                    alt="preview thumbnail"
                                    style={{ width: '70px', height: '70px', objectFit: 'cover', borderRadius: '12px', border: '1px solid #f3f4f6' }}
                                />
                            ))}
                            {/* 사진이 4장 이상일 경우 "+N" 형태로 표시 */}
                            {selectedFiles.length > 3 && (
                                <div style={{ width: '70px', height: '70px', borderRadius: '12px', backgroundColor: '#f3f4f6', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '14px', fontWeight: 'bold', color: '#6b7280' }}>
                                    +{selectedFiles.length - 3}
                                </div>
                            )}
                        </div>

                        {/* 💡 핵심 결과값 강조 박스 */}
                        <div style={{ backgroundColor: '#f8f9fa', padding: '15px', borderRadius: '16px', marginBottom: '25px' }}>
                            <div style={{ fontSize: '13px', color: '#6b7280', marginBottom: '5px' }}>추천 스타일링</div>
                            <div style={{ fontSize: '20px', fontWeight: '800', color: '#111827' }}>{result.prediction}</div>
                        </div>

                        {/* 버튼 영역 */}
                        <div style={{ display: 'flex', gap: '10px', justifyContent: 'center' }}>
                            <button onClick={() => setIsModalOpen(false)} style={{ flex: 1, padding: '14px', border: '1px solid #e5e7eb', borderRadius: '14px', cursor: 'pointer', backgroundColor: 'white', fontWeight: 'bold', color: '#374151' }}>
                                닫기
                            </button>
                            <button onClick={goToDetail} style={{ flex: 2, padding: '14px', backgroundColor: '#000', color: 'white', border: 'none', borderRadius: '14px', cursor: 'pointer', fontWeight: 'bold' }}>
                                상세 리포트 보기
                            </button>
                        </div>
                    </motion.div>
                </div>
            )}
        </div>
    );
}

export default App;