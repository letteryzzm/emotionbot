set(APP_PATH ${CMAKE_CURRENT_LIST_DIR})
set(APP_SRC ${APP_PATH}/src/main.c ${APP_PATH}/src/line_face.c ${APP_PATH}/src/eb2.c
            ${APP_PATH}/src/bench.cc ${APP_PATH}/src/models_data.cc
            ${APP_PATH}/src/ui_font_cn_18.c ${APP_PATH}/src/ui_font_cn_24.c)
add_library(${EXAMPLE_LIB})
target_sources(${EXAMPLE_LIB} PRIVATE ${APP_SRC})
add_subdirectory(${CMAKE_SOURCE_DIR}/examples/tflite/tflite-helloworld/tflite ${CMAKE_BINARY_DIR}/app_tflite)
