import * as THREE from 'three';

export class CADUtils {
    private static _checkerTexture: THREE.CanvasTexture;

    static get checkerTexture(): THREE.CanvasTexture {
        // if (!this._checkerTexture) {
        //     const canvas = document.createElement('canvas');
        //     canvas.width = 1024; canvas.height = 256;
        //     const ctx = canvas.getContext('2d');
            
        //     if (ctx) {
        //         ctx.fillStyle = '#2e7d32';
        //         ctx.fillRect(0, 0, 1024, 256);
                
        //         // ctx.fillStyle = '#e0e0e0';
        //         // const size = 32;
        //         // for(let i=0; i < 1024/size; i++) {
        //         //     for(let j=0; j < 256/size; j++) {
        //         //         if((i+j) % 2 === 0) ctx.fillRect(i*size, j*size, size, size);
        //         //     }
        //         // }
        //     }
        //     const texture = new THREE.CanvasTexture(canvas);
        //     texture.wrapS = THREE.RepeatWrapping;
        //     texture.wrapT = THREE.RepeatWrapping;
        //     this._checkerTexture = texture;
        // }
        return this._checkerTexture;
    }

    static createMesh(geometry: THREE.BufferGeometry, colorStr: string, texture: THREE.Texture | null = null, opacity = 1): THREE.Mesh {
        const transparent = opacity < 1;
        const materialOpts: THREE.MeshStandardMaterialParameters = {
            roughness: 0.7,
            metalness: 0.1,
            polygonOffset: true,
            polygonOffsetFactor: 1,
            polygonOffsetUnits: 1,
            side: THREE.DoubleSide,
            transparent,
            opacity,
            depthWrite: !transparent,
        };
        if (texture) {
            materialOpts.map = texture;
            materialOpts.color = new THREE.Color('#ffffff');
        } else {
            materialOpts.color = new THREE.Color(colorStr);
        }

        const material = new THREE.MeshStandardMaterial(materialOpts);
        const mesh = new THREE.Mesh(geometry, material);
        mesh.castShadow = true; mesh.receiveShadow = true;

        const edges = new THREE.EdgesGeometry(geometry);
        const line = new THREE.LineSegments(edges, new THREE.LineBasicMaterial({ color: 0x222222, linewidth: 1 }));
        mesh.add(line);
        
        return mesh;
    }

    static createElbow(color: string, opacity: number = 1, pathRadius: number = 1.2, outerRadius: number = 0.6, innerRadius: number = 0.45): THREE.Group {
        const group = new THREE.Group();
        
        // 질량 중심 보정
        const comOffset = (2 * pathRadius) / Math.PI; 
        
        // 파이프의 양 끝 단면(Cap)을 메우기 위해 RingGeometry 생성
        const capGeo = new THREE.RingGeometry(innerRadius, outerRadius, 16);
        
        const unrotatedGroup = new THREE.Group();
        
        // TorusGeometry 2개를 겹쳐서 속이 빈 파이프 효과 구현
        const outerGeo = new THREE.TorusGeometry(pathRadius, outerRadius, 16, 32, Math.PI/2);
        const innerGeo = new THREE.TorusGeometry(pathRadius, innerRadius, 16, 32, Math.PI/2);
        
        const torusOuter = this.createMesh(outerGeo, color, null, opacity);
        const torusInner = this.createMesh(innerGeo, '#546e7a', null, opacity);

        // 단면 1 (0도 위치)
        const cap1 = this.createMesh(capGeo, color, null, opacity);
        cap1.position.set(pathRadius, 0, 0);
        cap1.rotation.x = -Math.PI / 2;

        // 단면 2 (90도 위치)
        const cap2 = this.createMesh(capGeo, color, null, opacity);
        cap2.position.set(0, pathRadius, 0);
        cap2.rotation.y = Math.PI / 2;
        
        unrotatedGroup.add(torusOuter);
        unrotatedGroup.add(torusInner);
        unrotatedGroup.add(cap1);
        unrotatedGroup.add(cap2);
        
        // 만든 파이프 전체를 컨베이어에 눕게 회전
        unrotatedGroup.rotation.x = -Math.PI/2;
        
        // 중심을 질량 중심으로 이동시킴.
        unrotatedGroup.position.set(-3 * comOffset / 4, 0, 3 * comOffset / 4);
        
        // 바닥에 닿도록 보정
        unrotatedGroup.position.y += outerRadius/2;

        group.add(unrotatedGroup);
        return group;
    }

    static createDisk(radius: number, thickness: number, color: string, opacity = 1): THREE.Mesh {
        const geo = new THREE.CylinderGeometry(radius, radius, thickness, 32);
        return this.createMesh(geo, color, null, opacity);
    }

    static createCapsule(radius: number, length: number, color: string, opacity = 1): THREE.Group {
        const group = new THREE.Group();
        const cyl = this.createMesh(new THREE.CylinderGeometry(radius, radius, length, 32), color, null, opacity);
        group.add(cyl);

        const thickness = 0.05;

        const topHalf = this.createDisk(radius, thickness, color, opacity);
        topHalf.position.y = length / 2 + thickness / 2;
        group.add(topHalf);

        const botHalf = this.createDisk(radius, thickness, color, opacity);
        botHalf.position.y = -length / 2 - thickness / 2;
        group.add(botHalf);

        return group;
    }

    static createJointCapsule(radius: number, length: number, bodyColor: string, capColor: string, opacity = 1): THREE.Group {
        const group = new THREE.Group();
        const cyl = this.createMesh(new THREE.CylinderGeometry(radius, radius, length, 32), bodyColor, null, opacity);
        group.add(cyl);

        const thickness = 0.05;

        const botHalf = this.createDisk(radius, thickness, bodyColor, opacity);
        botHalf.position.y = -length / 2 - thickness / 2;
        group.add(botHalf);

        const topHalf = this.createDisk(radius, thickness, capColor, opacity);
        topHalf.position.y = length / 2 + thickness / 2;
        group.add(topHalf);

        return group;
    }

    static createRoundedBoxProfile(length: number, height: number, depth: number, color: string): THREE.Group {
        const group = new THREE.Group();
        const radius = height / 2;
        const boxLen = length - (radius * 2);
        
        const boxGeo = new THREE.BoxGeometry(boxLen, height, depth);
        const cylGeo = new THREE.CylinderGeometry(radius, radius, depth, 32);
        
        const box = this.createMesh(boxGeo, color);
        group.add(box);
        
        const cap1 = this.createMesh(cylGeo, color);
        cap1.rotation.x = Math.PI / 2;
        cap1.position.x = boxLen / 2;
        group.add(cap1);
        
        const cap2 = this.createMesh(cylGeo, color);
        cap2.rotation.x = Math.PI / 2;
        cap2.position.x = -boxLen / 2;
        group.add(cap2);
        
        return group;
    }

    static buildConveyorBody(length: number, useTexture: boolean = false): THREE.Group {
        const bodyGroup = new THREE.Group();
        const texture = useTexture ? this.checkerTexture : null;
        const originOffsetX = length / 2;

        // --- 메인 프로파일 (양쪽 가이드 레일) ---
        const profileL = this.createRoundedBoxProfile(length, 0.5, 0.3, '#b0b8c0');
        profileL.position.set(originOffsetX, 0, 2.15); 
        bodyGroup.add(profileL);

        const profileR = this.createRoundedBoxProfile(length, 0.5, 0.3, '#b0b8c0');
        profileR.position.set(originOffsetX, 0, -2.15);
        bodyGroup.add(profileR);

        // --- 롤러 (내부 구동축) ---
        const rollerGeo = new THREE.CylinderGeometry(0.15, 0.15, 4, 16);
        const rollerCount = Math.floor((length - 1) / 0.8);
        const startX = -(rollerCount - 1) * 0.8 / 2;
        for(let i=0; i<rollerCount; i++) {
            const roller = this.createMesh(rollerGeo, '#90959a');
            roller.rotation.x = Math.PI / 2;
            roller.position.set(originOffsetX + startX + (i * 0.8), 0.04, 0); 
            bodyGroup.add(roller);
        }

        // --- 벨트 (상단/하단 띠 및 양 끝 회전축(드럼)) ---
        const beltThickness = 0.06;
        const drumRadius = 0.25;
        const beltLength = length - (drumRadius * 2) - 0.1;

        const beltTopGeo = new THREE.BoxGeometry(beltLength, beltThickness, 3.9);
        const beltTop = this.createMesh(beltTopGeo, '#2e7d32', texture);
        beltTop.position.set(originOffsetX, drumRadius - beltThickness / 2, 0);
        bodyGroup.add(beltTop);

        const beltBotGeo = new THREE.BoxGeometry(beltLength, beltThickness, 3.9);
        const beltBot = this.createMesh(beltBotGeo, '#1b5e20'); 
        beltBot.position.set(originOffsetX, -(drumRadius - beltThickness / 2), 0);
        bodyGroup.add(beltBot);

        const drumGeo = new THREE.CylinderGeometry(drumRadius, drumRadius, 3.9, 32);
        const drumL = this.createMesh(drumGeo, '#2e7d32', texture);
        drumL.rotation.x = Math.PI / 2;
        drumL.position.set(originOffsetX - beltLength/2, 0, 0);
        bodyGroup.add(drumL);

        const drumR = this.createMesh(drumGeo, '#2e7d32', texture);
        drumR.rotation.x = Math.PI / 2;
        drumR.position.set(originOffsetX + beltLength/2, 0, 0);
        bodyGroup.add(drumR);

        return bodyGroup;
    }

    }
