import ctypes
import numpy as np
from OpenGL.EGL import *
from OpenGL.GL import *

display = eglGetDisplay(EGL_DEFAULT_DISPLAY)
eglInitialize(display, None, None)

config_attribs = np.array([
    EGL_SURFACE_TYPE, EGL_PBUFFER_BIT,
    EGL_BLUE_SIZE, 8,
    EGL_GREEN_SIZE, 8,
    EGL_RED_SIZE, 8,
    EGL_DEPTH_SIZE, 24,
    EGL_RENDERABLE_TYPE, EGL_OPENGL_BIT,
    EGL_NONE
], dtype=np.int32)

configs = (ctypes.c_void_p * 1)()
num_configs = ctypes.c_int()
eglChooseConfig(display, config_attribs, configs, 1, ctypes.byref(num_configs))
config = configs[0]

pbuffer_attribs = np.array([EGL_WIDTH, 800, EGL_HEIGHT, 600, EGL_NONE], dtype=np.int32)
surface = eglCreatePbufferSurface(display, config, pbuffer_attribs)

eglBindAPI(EGL_OPENGL_API)
context = eglCreateContext(display, config, EGL_NO_CONTEXT, None)
eglMakeCurrent(display, surface, surface, context)

fbo = glGenFramebuffers(1)
glBindFramebuffer(GL_FRAMEBUFFER, fbo)
color_rb = glGenRenderbuffers(1)
glBindRenderbuffer(GL_RENDERBUFFER, color_rb)
glRenderbufferStorage(GL_RENDERBUFFER, GL_RGBA8, 800, 600)
glFramebufferRenderbuffer(GL_FRAMEBUFFER, GL_COLOR_ATTACHMENT0, GL_RENDERBUFFER, color_rb)
status = glCheckFramebufferStatus(GL_FRAMEBUFFER)
print("FBO Complete:", status == GL_FRAMEBUFFER_COMPLETE)
