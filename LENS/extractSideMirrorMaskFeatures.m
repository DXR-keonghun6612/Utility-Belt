function [featureVector, featureNames, debugInfo] = extractSideMirrorMaskFeatures(BW, opts)
% extractSideMirrorMaskFeatures
% BW 사이드미러 실루엣 마스크에서 분류용 shape feature를 추출한다.
%
% 특징 설계 원칙:
%   1) scale invariance 제거:
%      - area, bbox size, radial distance 등을 raw pixel 또는 mm 단위로 유지
%
%   2) flip invariance 제거:
%      - 좌우/상하 signed area imbalance
%      - signed central moments
%      - Fourier phase-normalized real/imag feature 포함
%
%   3) PCA 기준각 흔들림 대응:
%      - PCA frame에서 radial profile 생성
%      - FFT magnitude
%      - phase-normalized Fourier descriptor 포함
%
% 입력:
%   BW   : binary mask image. logical 또는 numeric 가능.
%   opts : option struct. 생략 가능.
%
% 출력:
%   featureVector : 1 x D feature vector
%   featureNames  : 1 x D cell array
%   debugInfo     : 중간 계산 결과 확인용 struct

    if nargin < 2
        opts = struct();
    end

    opts = fillDefaultOptions(opts);

    % ------------------------------------------------------------
    % 1. Mask preprocessing
    % ------------------------------------------------------------
    BW = BW > 0;

    if opts.FillHoles
        BW = imfill(BW, 'holes');
    end

    if opts.UseLargestComponent
        BW = bwareafilt(BW, 1);
    end

    if ~any(BW(:))
        error('Input BW mask is empty.');
    end

    px = opts.PixelSize;   % 예: mm / pixel. 모르면 1 사용.

    % ------------------------------------------------------------
    % 2. Basic region properties
    % ------------------------------------------------------------
    stats = regionprops(BW, ...
        'Area', ...
        'Centroid', ...
        'BoundingBox', ...
        'MajorAxisLength', ...
        'MinorAxisLength', ...
        'Perimeter', ...
        'ConvexArea');

    stats = stats(1);

    area = stats.Area * px^2;
    perimeter = stats.Perimeter * px;

    centroid = stats.Centroid * px;
    cx = centroid(1);
    cy = centroid(2);

    bbox = stats.BoundingBox;
    bboxX = bbox(1) * px;
    bboxY = bbox(2) * px;
    bboxW = bbox(3) * px;
    bboxH = bbox(4) * px;
    bboxArea = bboxW * bboxH;

    bboxCx = bboxX + bboxW / 2;
    bboxCy = bboxY + bboxH / 2;

    majorAxisLength = stats.MajorAxisLength * px;
    minorAxisLength = stats.MinorAxisLength * px;
    convexArea = stats.ConvexArea * px^2;

    bboxAspect = safeDivide(bboxW, bboxH);
    axisRatio = safeDivide(majorAxisLength, minorAxisLength);
    extent = safeDivide(area, bboxArea);
    solidity = safeDivide(area, convexArea);
    circularity = safeDivide(4 * pi * area, perimeter^2);

    centroidDxFromBBox = cx - bboxCx;
    centroidDyFromBBox = cy - bboxCy;

    % ------------------------------------------------------------
    % 3. Pixel coordinate list
    % ------------------------------------------------------------
    [rows, cols] = find(BW);

    x = double(cols) * px;
    y = double(rows) * px;

    dx = x - cx;
    dy = y - cy;

    pixelArea = px^2;

    % ------------------------------------------------------------
    % 4. Image-frame signed asymmetry features
    % ------------------------------------------------------------
    areaRightCentroid = sum(x >= cx) * pixelArea;
    areaLeftCentroid  = sum(x <  cx) * pixelArea;
    areaDownCentroid  = sum(y >= cy) * pixelArea;
    areaUpCentroid    = sum(y <  cy) * pixelArea;

    imgAreaRightMinusLeftCentroid = areaRightCentroid - areaLeftCentroid;
    imgAreaDownMinusUpCentroid = areaDownCentroid - areaUpCentroid;

    areaRightBBox = sum(x >= bboxCx) * pixelArea;
    areaLeftBBox  = sum(x <  bboxCx) * pixelArea;
    areaDownBBox  = sum(y >= bboxCy) * pixelArea;
    areaUpBBox    = sum(y <  bboxCy) * pixelArea;

    imgAreaRightMinusLeftBBox = areaRightBBox - areaLeftBBox;
    imgAreaDownMinusUpBBox = areaDownBBox - areaUpBBox;

    % ------------------------------------------------------------
    % 5. PCA frame
    % ------------------------------------------------------------
    XY = [dx(:), dy(:)];

    C = cov(XY);
    [V, D] = eig(C);
    [~, idx] = sort(diag(D), 'descend');

    e1 = V(:, idx(1));  % major axis direction

    % PCA 축의 180도 부호 모호성 제거.
    % 여기서는 이미지 +x 방향과 같은 쪽을 +e1로 둔다.
    % 이 처리는 flip invariance를 만드는 것이 아니라,
    % PCA 부호가 샘플마다 뒤집히는 문제를 막기 위한 deterministic rule이다.
    if e1(1) < 0
        e1 = -e1;
    end

    % e2는 e1에 수직인 방향
    e2 = [-e1(2); e1(1)];

    xp = XY * e1;
    yp = XY * e2;

    pcaAngle = atan2(e1(2), e1(1));

    pcaAreaPosE1 = sum(xp >= 0) * pixelArea;
    pcaAreaNegE1 = sum(xp <  0) * pixelArea;
    pcaAreaPosE2 = sum(yp >= 0) * pixelArea;
    pcaAreaNegE2 = sum(yp <  0) * pixelArea;

    pcaAreaPosE1MinusNegE1 = pcaAreaPosE1 - pcaAreaNegE1;
    pcaAreaPosE2MinusNegE2 = pcaAreaPosE2 - pcaAreaNegE2;

    % ------------------------------------------------------------
    % 6. Signed central moments
    % ------------------------------------------------------------
    mu30_img = sum(dx.^3) * pixelArea;
    mu03_img = sum(dy.^3) * pixelArea;
    mu21_img = sum((dx.^2) .* dy) * pixelArea;
    mu12_img = sum(dx .* (dy.^2)) * pixelArea;

    mu30_pca = sum(xp.^3) * pixelArea;
    mu03_pca = sum(yp.^3) * pixelArea;
    mu21_pca = sum((xp.^2) .* yp) * pixelArea;
    mu12_pca = sum(xp .* (yp.^2)) * pixelArea;

    % 값 범위가 너무 커지는 것을 막기 위한 signed log compression.
    % scale 정보를 완전히 제거하는 정규화는 아니다.
    mu30_img_log = signedLog(mu30_img);
    mu03_img_log = signedLog(mu03_img);
    mu21_img_log = signedLog(mu21_img);
    mu12_img_log = signedLog(mu12_img);

    mu30_pca_log = signedLog(mu30_pca);
    mu03_pca_log = signedLog(mu03_pca);
    mu21_pca_log = signedLog(mu21_pca);
    mu12_pca_log = signedLog(mu12_pca);

    % ------------------------------------------------------------
    % 7. Boundary extraction
    % ------------------------------------------------------------
    boundaries = bwboundaries(BW, 'noholes');

    if isempty(boundaries)
        error('No boundary found from BW mask.');
    end

    boundaryLengths = cellfun(@(b) size(b, 1), boundaries);
    [~, bid] = max(boundaryLengths);
    boundary = boundaries{bid};

    by = double(boundary(:, 1)) * px;
    bx = double(boundary(:, 2)) * px;

    % ------------------------------------------------------------
    % 8. Radial profile in PCA frame
    % ------------------------------------------------------------
    N = opts.NumAngles;

    radialPCA = computeRadialProfile( ...
        bx, by, cx, cy, e1, e2, N);

    if opts.RadialSmoothWindow > 1
        radialPCA = circularMovingMean(radialPCA, opts.RadialSmoothWindow);
    end

    radialMean = mean(radialPCA);
    radialStd = std(radialPCA);
    radialMin = min(radialPCA);
    radialMax = max(radialPCA);
    radialRange = radialMax - radialMin;

    q = localPercentiles(radialPCA, [10 25 50 75 90]);

    radialP10 = q(1);
    radialP25 = q(2);
    radialP50 = q(3);
    radialP75 = q(4);
    radialP90 = q(5);

    % ------------------------------------------------------------
    % 9. Fourier features
    % ------------------------------------------------------------
    R = fft(radialPCA(:));

    K = min(opts.NumFourier, floor(N / 2) - 1);
    harmonicIdx = 1:K;
    fftIdx = harmonicIdx + 1;  % MATLAB fft index. R(1)은 DC.

    % FFT magnitude.
    % /N은 샘플 개수 영향 제거용이며, scale invariance를 만드는 것은 아니다.
    fftMag = abs(R(fftIdx)) / N;

    % Phase-normalized Fourier descriptor
    % PCA 각도 오차로 radial profile이 circular shift되는 문제를 줄이기 위한 특징.
    refMaxK = min(opts.PhaseReferenceMaxHarmonic, K);
    refCandidates = 1:refMaxK;

    R1 = R(2);
    energyLow = sum(abs(R(refCandidates + 1)));

    if abs(R1) > opts.PhaseReferenceThreshold * max(energyLow, eps)
        k0 = 1;
    else
        [~, localId] = max(abs(R(refCandidates + 1)));
        k0 = refCandidates(localId);
    end

    phi0 = angle(R(k0 + 1)) / k0;

    phaseNormReal = zeros(1, K);
    phaseNormImag = zeros(1, K);

    for ii = 1:K
        k = harmonicIdx(ii);
        Zk = R(k + 1) * exp(-1i * k * phi0);
        Zk = Zk / N;

        phaseNormReal(ii) = real(Zk);
        phaseNormImag(ii) = imag(Zk);
    end

    % ------------------------------------------------------------
    % 10. Optional bispectrum features
    % ------------------------------------------------------------
    bispecFeature = [];
    bispecNames = {};

    if opts.IncludeBispectrum
        BOrder = min(opts.BispectrumOrder, floor(K / 2));

        for p = 1:BOrder
            for qid = 1:BOrder
                if p + qid <= K
                    Bpq = R(p + 1) * R(qid + 1) * conj(R(p + qid + 1));
                    Bpq = Bpq / (N^3);

                    % 매우 큰 값이 나올 수 있으므로 signed log 사용
                    bispecFeature(end + 1) = signedLog(real(Bpq)); %#ok<AGROW>
                    bispecNames{end + 1} = sprintf('bispec_real_log_p%d_q%d', p, qid); %#ok<AGROW>

                    bispecFeature(end + 1) = signedLog(imag(Bpq)); %#ok<AGROW>
                    bispecNames{end + 1} = sprintf('bispec_imag_log_p%d_q%d', p, qid); %#ok<AGROW>
                end
            end
        end
    end

    % ------------------------------------------------------------
    % 11. Assemble feature vector
    % ------------------------------------------------------------
    scalarFeature = [
        area, ...
        perimeter, ...
        bboxW, ...
        bboxH, ...
        bboxArea, ...
        majorAxisLength, ...
        minorAxisLength, ...
        convexArea, ...
        bboxAspect, ...
        axisRatio, ...
        extent, ...
        solidity, ...
        circularity, ...
        centroidDxFromBBox, ...
        centroidDyFromBBox, ...
        imgAreaRightMinusLeftCentroid, ...
        imgAreaDownMinusUpCentroid, ...
        imgAreaRightMinusLeftBBox, ...
        imgAreaDownMinusUpBBox, ...
        pcaAreaPosE1MinusNegE1, ...
        pcaAreaPosE2MinusNegE2, ...
        mu30_img_log, ...
        mu03_img_log, ...
        mu21_img_log, ...
        mu12_img_log, ...
        mu30_pca_log, ...
        mu03_pca_log, ...
        mu21_pca_log, ...
        mu12_pca_log, ...
        cos(pcaAngle), ...
        sin(pcaAngle), ...
        radialMean, ...
        radialStd, ...
        radialMin, ...
        radialMax, ...
        radialRange, ...
        radialP10, ...
        radialP25, ...
        radialP50, ...
        radialP75, ...
        radialP90 ...
    ];

    scalarNames = {
        'area', ...
        'perimeter', ...
        'bbox_width', ...
        'bbox_height', ...
        'bbox_area', ...
        'major_axis_length', ...
        'minor_axis_length', ...
        'convex_area', ...
        'bbox_aspect_width_over_height', ...
        'axis_ratio_major_over_minor', ...
        'extent_area_over_bbox_area', ...
        'solidity_area_over_convex_area', ...
        'circularity', ...
        'centroid_dx_from_bbox_center', ...
        'centroid_dy_from_bbox_center', ...
        'img_area_right_minus_left_centroid', ...
        'img_area_down_minus_up_centroid', ...
        'img_area_right_minus_left_bbox', ...
        'img_area_down_minus_up_bbox', ...
        'pca_area_pos_e1_minus_neg_e1', ...
        'pca_area_pos_e2_minus_neg_e2', ...
        'mu30_img_signed_log', ...
        'mu03_img_signed_log', ...
        'mu21_img_signed_log', ...
        'mu12_img_signed_log', ...
        'mu30_pca_signed_log', ...
        'mu03_pca_signed_log', ...
        'mu21_pca_signed_log', ...
        'mu12_pca_signed_log', ...
        'pca_angle_cos', ...
        'pca_angle_sin', ...
        'radial_mean', ...
        'radial_std', ...
        'radial_min', ...
        'radial_max', ...
        'radial_range', ...
        'radial_p10', ...
        'radial_p25', ...
        'radial_p50', ...
        'radial_p75', ...
        'radial_p90' ...
    };

    radialFeature = radialPCA(:).';
    radialNames = cell(1, N);
    for i = 1:N
        radialNames{i} = sprintf('radial_pca_%03d', i);
    end

    fftMagFeature = fftMag(:).';
    fftMagNames = cell(1, K);
    for i = 1:K
        fftMagNames{i} = sprintf('fft_mag_k%d', i);
    end

    phaseFeature = zeros(1, 2 * K);
    phaseNames = cell(1, 2 * K);

    for i = 1:K
        phaseFeature(2 * i - 1) = phaseNormReal(i);
        phaseFeature(2 * i) = phaseNormImag(i);

        phaseNames{2 * i - 1} = sprintf('phase_norm_real_k%d', i);
        phaseNames{2 * i} = sprintf('phase_norm_imag_k%d', i);
    end

    featureVector = [
        scalarFeature, ...
        radialFeature, ...
        fftMagFeature, ...
        phaseFeature, ...
        bispecFeature ...
    ];

    featureNames = [
        scalarNames, ...
        radialNames, ...
        fftMagNames, ...
        phaseNames, ...
        bispecNames ...
    ];

    % ------------------------------------------------------------
    % 12. Debug output
    % ------------------------------------------------------------
    debugInfo = struct();
    debugInfo.BW = BW;
    debugInfo.centroid = [cx, cy];
    debugInfo.bbox = [bboxX, bboxY, bboxW, bboxH];
    debugInfo.pca_e1 = e1;
    debugInfo.pca_e2 = e2;
    debugInfo.pca_angle = pcaAngle;
    debugInfo.boundary_x = bx;
    debugInfo.boundary_y = by;
    debugInfo.radialPCA = radialPCA;
    debugInfo.fftR = R;
    debugInfo.phaseReferenceHarmonic = k0;
    debugInfo.phaseReferenceAngle = phi0;
end


% ========================================================================
% Local helper functions
% ========================================================================

function opts = fillDefaultOptions(opts)
    if ~isfield(opts, 'PixelSize')
        opts.PixelSize = 1;
    end

    if ~isfield(opts, 'NumAngles')
        opts.NumAngles = 256;
    end

    if ~isfield(opts, 'NumFourier')
        opts.NumFourier = 20;
    end

    if ~isfield(opts, 'FillHoles')
        opts.FillHoles = true;
    end

    if ~isfield(opts, 'UseLargestComponent')
        opts.UseLargestComponent = true;
    end

    if ~isfield(opts, 'RadialSmoothWindow')
        opts.RadialSmoothWindow = 3;
    end

    if ~isfield(opts, 'PhaseReferenceMaxHarmonic')
        opts.PhaseReferenceMaxHarmonic = 8;
    end

    if ~isfield(opts, 'PhaseReferenceThreshold')
        opts.PhaseReferenceThreshold = 1e-3;
    end

    if ~isfield(opts, 'IncludeBispectrum')
        opts.IncludeBispectrum = false;
    end

    if ~isfield(opts, 'BispectrumOrder')
        opts.BispectrumOrder = 6;
    end
end


function rProfile = computeRadialProfile(bx, by, cx, cy, e1, e2, N)
% PCA 좌표계에서 중심-외곽 radial distance profile 생성.
% 한 angle bin에 contour 점이 여러 개 들어가면 max radius 사용.

    dx = bx(:) - cx;
    dy = by(:) - cy;

    u = dx * e1(1) + dy * e1(2);
    v = dx * e2(1) + dy * e2(2);

    theta = atan2(v, u);
    theta(theta < 0) = theta(theta < 0) + 2 * pi;

    r = hypot(u, v);

    bin = floor(theta / (2 * pi) * N) + 1;
    bin(bin < 1) = 1;
    bin(bin > N) = N;

    rProfile = accumarray(bin, r, [N, 1], @max, NaN);

    rProfile = fillCircularNaN(rProfile);
    rProfile = rProfile(:).';
end


function y = fillCircularNaN(x)
% circular signal의 NaN bin을 보간한다.

    x = x(:);
    N = numel(x);

    idx = (1:N).';
    valid = ~isnan(x);

    if all(valid)
        y = x;
        return;
    end

    if ~any(valid)
        error('All radial bins are NaN.');
    end

    validIdx = idx(valid);
    validVal = x(valid);

    extIdx = [validIdx - N; validIdx; validIdx + N];
    extVal = [validVal; validVal; validVal];

    y = interp1(extIdx, extVal, idx, 'linear');
end


function y = circularMovingMean(x, win)
% circular moving average.
% radial profile의 시작/끝 경계가 끊기지 않도록 양끝을 wrap한다.

    x = x(:).';
    N = numel(x);

    win = max(1, round(win));

    if win <= 1
        y = x;
        return;
    end

    pad = floor(win / 2);

    xPad = [x(end - pad + 1:end), x, x(1:pad)];
    yPad = movmean(xPad, win);

    y = yPad(pad + 1:pad + N);
end


function y = safeDivide(a, b)
    if abs(b) < eps
        y = 0;
    else
        y = a / b;
    end
end


function y = signedLog(x)
    y = sign(x) .* log1p(abs(x));
end


function q = localPercentiles(x, pList)
% prctile 의존성을 줄이기 위한 간단한 percentile 계산

    x = sort(x(:));
    N = numel(x);

    q = zeros(size(pList));

    for i = 1:numel(pList)
        p = pList(i);

        pos = 1 + (N - 1) * p / 100;
        lo = floor(pos);
        hi = ceil(pos);

        if lo == hi
            q(i) = x(lo);
        else
            alpha = pos - lo;
            q(i) = (1 - alpha) * x(lo) + alpha * x(hi);
        end
    end
end
